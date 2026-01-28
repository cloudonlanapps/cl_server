#!/usr/bin/env python3
"""
Performance Profiling Script for Full Embedding Flow

Usage:
    uv run profile_perf --auth-url <url> --store-url <url> --compute-url <url> --username <user> --password <pass>

This script:
1. Prepares unique copies of test images (modifying 1 pixel to ensure server-side hashing treats them as new).
2. Uploads images to the store.
3. Monitors the compute job status until completion.
4. Reports detailed timing metrics.
"""

import asyncio
import os
import random
import time
import uuid
import click
from pathlib import Path
from typing import List, Tuple

from PIL import Image
from rich.console import Console
from rich.table import Table

from cl_client import StoreManager, SessionManager, ServerConfig
from cl_client.store_models import StoreOperationResult
from loguru import logger
import sys

# Initialize Rich console
console = Console()

# Default test images location
TEST_VECTORS_DIR = Path(
    os.getenv("TEST_VECTORS_DIR", "/Users/anandasarangaram/Work/cl_server_test_media")
)

# Test images with expected face counts (same as integration test)
TEST_IMAGES = [
     ("test_face_single.jpg", 2),
     ("test_image_1920x1080.jpg", 0),  # No face
     ("IMG20240901130125.jpg", 3),
     ("IMG20240901202523.jpg", 5),
     ("IMG20240901194834.jpg", 3),
     ("IMG20240901193819.jpg", 11), 
     ("IMG20240901153107.jpg", 1),
]

def create_pixel_modified_copy(source_path: Path, dest_path: Path) -> None:
    """
    Create a unique copy of the image by modifying the first pixel.
    Crucially, this PRESERVES EXIF metadata.
    """
    try:
        with Image.open(source_path) as img:
            # Load pixel data
            pixels = img.load()
            
            # Modify first pixel slightly (add 1 to first channel)
            # This changes the bitstream, ensuring standard hashing algorithms produce a new hash
            # without visually affecting the image.
            # Generate a new random UUID
            unique_id = uuid.uuid4().bytes

            # Modify LAST 16 pixels (bottom-right) using the UUID bytes
            # This is safer than top-left to avoid interfering with face detection
            # (faces are rarely in the extreme bottom-right corner)
            if img.mode == 'RGB' or img.mode == 'RGBA':
                width, height = img.size
                total_pixels = width * height
                
                # Start from the last pixel and go backwards
                for i, byte in enumerate(unique_id):
                    # Calculate index from end
                    idx = total_pixels - 1 - i
                    
                    x = idx % width
                    y = idx // width
                    
                    pixel = list(img.getpixel((x, y)))
                    pixel[0] = byte # Set red channel to random byte from UUID
                    
                    if img.mode == 'RGBA':
                        img.putpixel((x, y), tuple(pixel))
                    else:
                        img.putpixel((x, y), tuple(pixel[:3]))
            
            # Get original EXIF
            exif_data = img.getexif()
            
            # Save to new path with EXIF
            img.save(dest_path, exif=exif_data, quality=95)
            
    except Exception as e:
        console.print(f"[bold red]Error preparing image {source_path}: {e}[/bold red]")
        raise

async def run_profile(
    auth_url: str,
    store_url: str,
    compute_url: str,
    username: str,
    password: str
):
    # 1. Setup Session
    config = ServerConfig(
        auth_url=auth_url,
        store_url=store_url,
        compute_url=compute_url,
    )
    
    console.print(f"[bold blue]Connecting to services...[/bold blue]")
    console.print(f"Auth: {auth_url}")
    console.print(f"Store: {store_url}")
    
    session = SessionManager(server_config=config)
    try:
        await session.login(username, password)
        console.print("[green]Login successful[/green]")
        
        store_manager = session.create_store_manager(timeout=300.0)
        async with store_manager:
            
            # 2. Prepare Data (Excluded from profiling time)
            console.print("\n[bold yellow]Preparing Test Images (Unique Copies)...[/bold yellow]")
            temp_dir = Path("/tmp/cl_perf_test_" + uuid.uuid4().hex)
            temp_dir.mkdir(parents=True, exist_ok=True)
            
            prepared_images: List[Tuple[str, Path, int]] = []
            
            for filename, expected_faces in TEST_IMAGES:
                source = TEST_VECTORS_DIR / "images" / filename
                if not source.exists():
                    console.print(f"[red]Warning: Source image {source} not found, skipping.[/red]")
                    continue
                    
                dest = temp_dir / f"unique_{uuid.uuid4().hex}_{filename}"
                create_pixel_modified_copy(source, dest)
                prepared_images.append((filename, dest, expected_faces))
                console.print(f"  Prepared: {filename} -> {dest.name}")

            if not prepared_images:
                console.print("[red]No images found to test![/red]")
                return

            console.print(f"Prepared {len(prepared_images)} images.")
            
            # 3. Start Profiling
            console.print("\n[bold green]Starting Benchmark...[/bold green]")
            
            start_time = time.perf_counter()
            
            upload_tasks = []
            
            # Helper for already completed tasks
            # Helper for already completed tasks
            async def already_completed(id):
                 return EntityStatusPayload(
                     entity_id=id,
                     status="completed",
                     timestamp=int(time.time() * 1000)
                 )

            # Upload Phase
            for filename, path, _ in prepared_images:
                label = f"PerfTest {filename} {start_time}"
                task = store_manager.create_entity(
                    is_collection=False,
                    label=label,
                    image_path=path
                )
                upload_tasks.append(task)
            
            results = await asyncio.gather(*upload_tasks)
            
            upload_end_time = time.perf_counter()
            upload_duration = upload_end_time - start_time
            console.print(f"Uploads initiated in {upload_duration:.3f}s")
            
            # Monitor Phase
            monitor_tasks = []
            entities = []
            
            for i, result in enumerate(results):
                result: StoreOperationResult = result
                if result.is_success:
                    entity = result.value_or_throw()
                    entities.append(entity)
                    # Check if already completed (e.g. duplicate upload)
                    if entity.intelligence_status == "completed":
                        console.print(f"  [green]Entity {entity.id} already completed (fast-tracked).[/green]")
                        # Log completion
                        # Log completion
                        logger.info(f"Image {entity.id} already completed")
                        monitor_tasks.append(already_completed(entity.id))
                    else:
                        # Start waiting for this entity
                        task = store_manager.wait_for_entity_status(
                            entity_id=entity.id,
                            target_status="completed",
                            timeout=300.0
                        )
                        # Wrap task to log completion
                        async def logged_wait(t, eid):
                            res = await t
                            logger.info(f"Image {eid} processing completed")
                            return res
                            
                        monitor_tasks.append(logged_wait(task, entity.id))
                else:
                    console.print(f"[red]Failed to upload image {i}: {result.error}[/red]")
            
            if not monitor_tasks:
                console.print("[red]All uploads failed, aborting.[/red]")
                return

            console.print(f"Monitoring {len(monitor_tasks)} jobs...")
            
            # Wait for all to complete
            wait_results = await asyncio.gather(*monitor_tasks, return_exceptions=True)
            
            end_time = time.perf_counter()
            total_duration = end_time - start_time
            
            # 4. Reporting
            console.print("\n[bold white on blue]--- Performance Report ---[/bold white on blue]")
            
            table = Table(title="Job Completion Statistics")
            table.add_column("Entity ID", style="cyan")
            table.add_column("Status", style="magenta")
            table.add_column("Details", style="green")
            
            success_count = 0
            
            for i, res in enumerate(wait_results):
                entity_id = entities[i].id
                if isinstance(res, Exception):
                     table.add_row(str(entity_id), "FAILED", str(res))
                else:
                     table.add_row(str(entity_id), "COMPLETED", f"Final Status: {res.status}")
                     success_count += 1
            
            console.print(table)
            
            console.print(f"\n[bold]Summary:[/bold]")
            console.print(f"Total Images: {len(prepared_images)}")
            console.print(f"Successful:   {success_count}")
            console.print(f"Total Time:   [bold green]{total_duration:.3f}s[/bold green]")
            console.print(f"Avg Time/Img: {total_duration/len(monitor_tasks):.3f}s")

            # Cleanup (Optional, but currently skipping as per plan to allow inspection)
            # console.print("\n[dim]Skipping cleanup to allow server log inspection...[/dim]")

    finally:
        await session.close()
        # Clean up temp local files
        try:
            import shutil
            shutil.rmtree(temp_dir)
        except:
            pass



@click.command()
@click.option("--auth-url", default="http://localhost:8010", help="Auth Service URL")
@click.option("--store-url", default="http://localhost:8011", help="Store Service URL")
@click.option("--compute-url", default="http://localhost:8012", help="Compute Service URL")
@click.option("--username", default="admin", help="Username")
@click.option("--password", default="admin", help="Password")
def main(auth_url, store_url, compute_url, username, password):
    # Configure loguru to suppress DEBUG logs from libraries
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    
    asyncio.run(run_profile(auth_url, store_url, compute_url, username, password))

if __name__ == "__main__":
    main()
