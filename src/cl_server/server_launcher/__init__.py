import os
import signal
import socket
import subprocess
import sys
import threading
import time
from argparse import ArgumentParser, Namespace
from pathlib import Path
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


def check_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a port is open on the given host."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, socket.error, ConnectionRefusedError):
        return False


def get_process_using_port(port: int) -> list[dict[str, str]]:
    """Get information about processes using the specified port.

    Returns a list of dicts with keys: 'pid', 'command', 'user'
    """
    try:
        # Use lsof to find processes using the port
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            pids = result.stdout.strip().split("\n")
            processes = []
            for pid in pids:
                # Get process details
                try:
                    ps_result = subprocess.run(
                        ["ps", "-p", pid, "-o", "pid=,user=,comm="],
                        capture_output=True,
                        text=True,
                        timeout=2,
                    )
                    if ps_result.returncode == 0:
                        parts = ps_result.stdout.strip().split(None, 2)
                        if len(parts) >= 3:
                            processes.append({
                                "pid": parts[0],
                                "user": parts[1],
                                "command": parts[2],
                            })
                except Exception:
                    pass
            return processes
        return []
    except Exception:
        return []


def kill_processes_on_port(port: int) -> bool:
    """Kill all processes using the specified port.

    Returns True if successful, False otherwise.
    """
    processes = get_process_using_port(port)
    if not processes:
        return True

    logger.info(f"Found {len(processes)} process(es) using port {port}")
    for proc in processes:
        logger.info(f"  PID {proc['pid']}: {proc['command']} (user: {proc['user']})")

    try:
        for proc in processes:
            pid = int(proc["pid"])
            logger.info(f"Killing process {pid}...")
            os.kill(pid, signal.SIGTERM)

        # Wait a bit for graceful shutdown
        time.sleep(2)

        # Check if any processes are still alive and force kill them
        remaining = get_process_using_port(port)
        if remaining:
            logger.warning(f"Some processes still alive on port {port}, force killing...")
            for proc in remaining:
                try:
                    pid = int(proc["pid"])
                    os.kill(pid, signal.SIGKILL)
                except Exception as e:
                    logger.error(f"Failed to kill PID {pid}: {e}")
            time.sleep(1)

        # Final check
        if not get_process_using_port(port):
            logger.success(f"Successfully freed port {port}")
            return True
        else:
            logger.error(f"Failed to free port {port}")
            return False

    except Exception as e:
        logger.error(f"Error killing processes on port {port}: {e}")
        return False


def check_mqtt_running() -> bool:
    """Check if MQTT broker is running on localhost:1883."""
    return check_port_open("localhost", 1883)


def check_qdrant_running() -> bool:
    """Check if Qdrant vector store is running on localhost:6333."""
    try:
        response = requests.get("http://localhost:6333/health", timeout=2)
        return response.ok
    except requests.RequestException:
        # Fallback to port check if health endpoint fails
        return check_port_open("localhost", 6333, timeout=1.0)


def start_mqtt_broker(env: dict[str, str]) -> bool:
    """Start MQTT broker using the docker start script."""
    logger.info("MQTT broker not running, attempting to start...")

    # Find the mqtt_broker_start script
    script_path = Path(__file__).parent.parent.parent.parent / "dockers" / "mosquitto_mqtt" / "bin" / "mqtt_broker_start"

    if not script_path.exists():
        logger.error(f"MQTT start script not found at: {script_path}")
        return False

    try:
        # Run the start script with the environment
        result = subprocess.run(
            [str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            logger.success("MQTT broker started successfully")
            return True
        else:
            logger.error(f"Failed to start MQTT broker: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("MQTT broker start script timed out")
        return False
    except Exception as e:
        logger.error(f"Error starting MQTT broker: {e}")
        return False


def start_qdrant_vectorstore(env: dict[str, str]) -> bool:
    """Start Qdrant vector store using the docker start script."""
    logger.info("Qdrant vector store not running, attempting to start...")

    # Find the vector_store_start script
    script_path = Path(__file__).parent.parent.parent.parent / "dockers" / "qdrant_vector_store" / "bin" / "vector_store_start"

    if not script_path.exists():
        logger.error(f"Qdrant start script not found at: {script_path}")
        return False

    try:
        # Run the start script with the environment
        result = subprocess.run(
            [str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode == 0:
            logger.success("Qdrant vector store started successfully")
            return True
        else:
            logger.error(f"Failed to start Qdrant vector store: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Qdrant start script timed out")
        return False
    except Exception as e:
        logger.error(f"Error starting Qdrant vector store: {e}")
        return False


shutdown_event = threading.Event()


def get_local_ip() -> str:
    """Get the local IP address of the machine."""
    try:
        # Create a socket connection to determine the local IP
        # This doesn't actually connect, just determines which interface would be used
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        # Fallback to localhost if we can't determine the IP
        return "127.0.0.1"


def print_env_export(cfg) -> None:
    """Print environment variables in .bashrc format."""
    local_ip = get_local_ip()

    print("\n" + "=" * 50)
    print("########## BEGIN ##########")
    print("# CLServer Env")
    print(f"export CL_AUTH_URL=http://{local_ip}:{cfg.auth.port}")
    print(f"export CL_COMPUTE_URL=http://{local_ip}:{cfg.compute.port}")
    print(f"export CL_STORE_URL=http://{local_ip}:{cfg.store.port}")
    print(f"export CL_MQTT_URL={cfg.mqtt_url}")
    print(f"export CL_QDRANT_URL=http://{local_ip}:6333")
    print("########## END ##########")
    print("=" * 50 + "\n")


def check_and_free_port(port: int, service_name: str, force: bool) -> bool:
    """Check if port is available and optionally free it.

    Args:
        port: Port number to check
        service_name: Name of the service for logging
        force: If True, kill processes using the port. If False, exit with error.

    Returns:
        True if port is available, False otherwise
    """
    if not check_port_open("localhost", port):
        # Port is free
        return True

    # Port is in use
    processes = get_process_using_port(port)
    if not processes:
        logger.warning(f"Port {port} appears to be in use but cannot identify processes")
        if force:
            logger.info("--force specified, attempting to start anyway...")
            return True
        else:
            logger.error(f"Port {port} required by {service_name} is already in use")
            logger.error("Use --force to kill existing processes, or manually stop them")
            return False

    logger.warning(f"Port {port} required by {service_name} is already in use:")
    for proc in processes:
        logger.warning(f"  PID {proc['pid']}: {proc['command']} (user: {proc['user']})")

    if force:
        logger.info(f"--force specified, killing processes on port {port}...")
        if kill_processes_on_port(port):
            return True
        else:
            logger.error(f"Failed to free port {port} for {service_name}")
            return False
    else:
        logger.error(f"Cannot start {service_name} because port {port} is in use")
        logger.error("Options:")
        logger.error("  1. Use --force flag to automatically kill existing processes")
        logger.error(f"  2. Manually kill the process: kill {processes[0]['pid']}")
        logger.error("  3. Stop the existing service before starting a new one")
        return False


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
    services: str
    force: bool

    def __init__(self, config: str = "", services: str = "all", force: bool = False):
        self.config = config
        self.services = services
        self.force = force
        super().__init__()


def main():
    parser = ArgumentParser()
    _ = parser.add_argument("--config", required=True)
    _ = parser.add_argument(
        "--services",
        default="all",
        help="Comma-separated list of services to start: auth,compute,store,m_insight,workers or 'all'",
    )
    _ = parser.add_argument(
        "--force",
        action="store_true",
        help="Force kill any existing processes on the required ports before starting",
    )
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

    # Check and start MQTT broker if needed
    logger.info("Checking MQTT broker status...")
    if not check_mqtt_running():
        logger.warning("MQTT broker is not running")
        if not start_mqtt_broker(env):
            sys.exit("[ERROR] Failed to start MQTT broker. Please check the logs and try starting it manually.")
    else:
        logger.success("MQTT broker is already running")

    # Check and start Qdrant vector store if needed
    logger.info("Checking Qdrant vector store status...")
    if not check_qdrant_running():
        logger.warning("Qdrant vector store is not running")
        if not start_qdrant_vectorstore(env):
            sys.exit("[ERROR] Failed to start Qdrant vector store. Please check the logs and try starting it manually.")
    else:
        logger.success("Qdrant vector store is already running")

    services = build_services(cfg, env)
    processes = Processes()

    requested_services = set(args.services.split(",")) if args.services != "all" else {"all"}

    def should_start(name: str) -> bool:
        return "all" in requested_services or name in requested_services

    try:
        # Run database migrations before starting services
        logger.info("Running database migrations...")
        if should_start("auth") and not migrate_auth(cfg.auth.dir, env):
            sys.exit("[ERROR] Auth service migration failed")
        if should_start("compute") and not migrate_compute(cfg.compute.dir, env):
            sys.exit("[ERROR] Compute service migration failed")
        if should_start("store") and not migrate_store(cfg.store.dir, env):
            sys.exit("[ERROR] Store service migration failed")

        # Start auth (required by all other services)
        if should_start("auth"):
            if not check_and_free_port(cfg.auth.port, "auth", args.force):
                sys.exit(f"[ERROR] Cannot start auth service - port {cfg.auth.port} is in use")
            logger.info(f"Starting auth server @ port {cfg.auth.port}...")
            processes.auth = start_process(services.auth)
            wait_for_server(cfg.auth_url)
            logger.success("auth service started")

        # Start compute (required by store and workers)
        if should_start("compute"):
            if not check_and_free_port(cfg.compute.port, "compute", args.force):
                sys.exit(f"[ERROR] Cannot start compute service - port {cfg.compute.port} is in use")
            logger.info(f"Starting compute server @ port {cfg.compute.port}...")
            processes.compute = start_process(services.compute)

            # Wait for compute to load auth module and cache public key
            time.sleep(1)
            wait_for_server(cfg.compute_url)
            logger.success("compute service started")

        # Start store (requires auth and compute)
        if should_start("store"):
            if not check_and_free_port(cfg.store.port, "store", args.force):
                sys.exit(f"[ERROR] Cannot start store service - port {cfg.store.port} is in use")
            logger.info(f"Starting store server @ port {cfg.store.port}...")
            processes.store = start_process(services.store)

            # Wait for store to load auth module and cache public key
            time.sleep(1)
            wait_for_server(cfg.store_url)
            logger.success("store service started")

        # Start m_insight (requires store)
        if should_start("m_insight"):
            logger.info("Starting m_insight worker...")
            processes.m_insight = start_process(services.m_insight)
            # m_insight has no HTTP health check, simple sleep to ensure startup
            time.sleep(1)
            logger.success("m_insight worker started")

        # Start workers (require auth and compute)
        if should_start("workers"):
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

        # Print environment variables for easy export
        print_env_export(cfg)

        logger.success("Press Ctrl+C / Ctrl+\\ to stop.")
        _ = shutdown_event.wait()

    finally:
        stop_all_processes(processes, cfg)
