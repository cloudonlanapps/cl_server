import os
import signal
import sys
import threading
import time
from argparse import ArgumentParser, Namespace
from typing import TYPE_CHECKING, Any

import requests
from loguru import logger

from .config import load_config
from .migrate import migrate_auth, migrate_compute, migrate_store
from .process import Processes, start_process, stop_all_processes
from .services import build_services

if TYPE_CHECKING:
    from types import FrameType
else:
    FrameType = Any  # type: ignore[misc]


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


def _handle_signal(signum: int, frame: FrameType | None) -> None:
    """Handle shutdown signals safely without reentrant I/O."""
    # Use os.write for async-signal-safe I/O instead of print or logging
    _ = frame
    msg = f"\nReceived signal {signum}, shutting down…\n"
    try:
        _ = os.write(sys.stderr.fileno(), msg.encode())
    except OSError:
        # If stderr write fails, just silently set the event
        pass
    shutdown_event.set()


class Args(Namespace):
    config: str

    def __init__(self, config: str = ""):
        self.config = config
        super().__init__()


def main():
    parser = ArgumentParser()
    _ = parser.add_argument("--config", required=True)
    args = parser.parse_args(namespace=Args())

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
        if not migrate_compute(cfg.compute.dir, env):
            sys.exit("[ERROR] Compute service migration failed")
        if not migrate_store(cfg.store.dir, env):
            sys.exit("[ERROR] Store service migration failed")

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

        # Start m_insight (requires store)
        logger.info("Starting m_insight worker...")
        processes.m_insight = start_process(services.m_insight)
        # m_insight has no HTTP health check, simple sleep to ensure startup
        time.sleep(1)
        logger.success("m_insight worker started")

        # Start workers (require auth and compute)
        for i, worker_service in enumerate(services.workers):
            logger.info(
                f"Starting worker {i + 1}/{len(services.workers)} : listening to {cfg.compute.port}"
            )
            processes.workers.append(start_process(worker_service))
            logger.success(f"worker {i + 1}/{len(services.workers)} started")

        # Signals
        _ = signal.signal(signal.SIGINT, _handle_signal)  # Ctrl+C
        _ = signal.signal(signal.SIGQUIT, _handle_signal)  # Ctrl+\
        _ = signal.signal(signal.SIGTERM, _handle_signal)

        logger.success("All services started. Press Ctrl+C / Ctrl+\\ to stop.")
        _ = shutdown_event.wait()

    finally:
        stop_all_processes(processes, cfg)
