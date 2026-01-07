import argparse
import os
import signal
import sys
import threading

from .config import load_config
from .services import build_services
from .process import start_process, stop_all_processes, Processes
from .verify import (
    wait_for_server,
    verify_compute_auth_from_root,
    set_store_guest_mode,
    verify_store_guest_mode,
)

shutdown_event = threading.Event()


def _handle_signal(signum, frame):
    print(f"\nReceived signal {signum}, shutting down…")
    shutdown_event.set()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()

    cfg = load_config(args.config)
    admin_password = os.environ.get("TEST_ADMIN_PASSWORD")
    if not admin_password:
        sys.exit("[ERROR] TEST_ADMIN_PASSWORD environment variable is required")

    env = os.environ | {
        "CL_SERVER_DIR": str(cfg.data_dir),
    }

    services = build_services(cfg, env)
    processes = Processes()

    try:
        # Start auth
        processes.auth = start_process(services.auth)
        wait_for_server(cfg.auth_url)

        # Start store
        processes.store = start_process(services.store)
        wait_for_server(cfg.store_url)

        # Start compute
        processes.compute = start_process(services.compute)
        wait_for_server(cfg.compute_url)

        # Verify compute auth
        verify_compute_auth_from_root(
            cfg.compute_url,
            cfg.compute_auth_required,
        )

        # Configure store
        set_store_guest_mode(
            cfg.auth_url,
            cfg.store_url,
            admin_password,
            cfg.store_guest_mode,
        )
        verify_store_guest_mode(cfg.store_url, cfg.store_guest_mode)

        # Start worker
        processes.worker = start_process(services.worker)

        # Signals
        signal.signal(signal.SIGINT, _handle_signal)  # Ctrl+C
        signal.signal(signal.SIGQUIT, _handle_signal)  # Ctrl+\
        signal.signal(signal.SIGTERM, _handle_signal)

        print("All services started. Press Ctrl+C / Ctrl+\\ to stop.")
        shutdown_event.wait()

    finally:
        stop_all_processes(processes)
