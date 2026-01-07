import argparse
import os
import signal
import sys
import threading
import time
import requests
from loguru import logger

from .config import load_config
from .services import build_services
from .process import start_process, stop_all_processes, Processes
from .migrate import migrate_auth, migrate_store, migrate_compute


def wait_for_server(url: str, timeout: int = 30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(url, timeout=1)
            if r.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(1)
    raise RuntimeError(f"Server did not become ready: {url}")


shutdown_event = threading.Event()


def _handle_signal(signum, frame):
    """Handle shutdown signals safely without reentrant I/O."""
    # Use os.write for async-signal-safe I/O instead of print or logging
    import errno

    msg = f"\nReceived signal {signum}, shutting down…\n"
    try:
        os.write(sys.stderr.fileno(), msg.encode())
    except OSError:
        # If stderr write fails, just silently set the event
        pass
    shutdown_event.set()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)

    # Ensure data directory exists (required for migrations and services)
    try:
        cfg.data_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        sys.exit(f"[ERROR] Failed to create data directory {cfg.data_dir}: {e}")

    env = os.environ | {
        "CL_SERVER_DIR": str(cfg.data_dir),
    }

    services = build_services(cfg, env)
    processes = Processes()

    try:
        # Run database migrations before starting services
        logger.info("Running database migrations...")
        if not migrate_auth(cfg.auth.dir, env):
            sys.exit("[ERROR] Auth service migration failed")
        if not migrate_store(cfg.store.dir, env):
            sys.exit("[ERROR] Store service migration failed")
        if not migrate_compute(cfg.compute.dir, env):
            sys.exit("[ERROR] Compute service migration failed")

        # Start auth (required by all other services)
        logger.info(f"Starting auth server @ port {cfg.auth.port}...")
        processes.auth = start_process(services.auth)
        wait_for_server(cfg.auth_url)
        logger.success("auth service started")

        # Start compute (required by store and workers)
        logger.info(f"Starting compute server @ port {cfg.compute.port}...")
        processes.compute = start_process(services.compute)

        # Wait for compute to load auth module and cache public key
        time.sleep(1)
        wait_for_server(cfg.compute_url)
        logger.success("compute service started")

        # Start store (requires auth and compute)
        logger.info(f"Starting store server @ port {cfg.store.port}...")
        processes.store = start_process(services.store)

        # Wait for store to load auth module and cache public key
        time.sleep(1)
        wait_for_server(cfg.store_url)
        logger.success("store service started")

        # Start workers (require auth and compute)
        for i, worker_service in enumerate(services.workers):
            logger.info(
                f"Starting worker {i + 1}/{len(services.workers)} : listening to {cfg.compute.port}"
            )
            processes.workers.append(start_process(worker_service))
            logger.success(f"worker {i + 1}/{len(services.workers)} started")

        # Signals
        signal.signal(signal.SIGINT, _handle_signal)  # Ctrl+C
        signal.signal(signal.SIGQUIT, _handle_signal)  # Ctrl+\
        signal.signal(signal.SIGTERM, _handle_signal)

        logger.success("All services started. Press Ctrl+C / Ctrl+\\ to stop.")
        shutdown_event.wait()

    finally:
        stop_all_processes(processes, cfg)
