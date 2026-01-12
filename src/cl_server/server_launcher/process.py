import os
import signal
import subprocess
import time

import requests
from loguru import logger
from pydantic import BaseModel

from .config import Config
from .services import ServiceArgs


class Processes(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    auth: subprocess.Popen[str] | None = None
    store: subprocess.Popen[str] | None = None
    compute: subprocess.Popen[str] | None = None
    workers: list[subprocess.Popen[str]] = []


def start_process(service: ServiceArgs) -> subprocess.Popen[str]:
    """Start a service subprocess.

    Args:
        service: Service configuration with command, working directory, environment, and log file

    Returns:
        subprocess.Popen: The started process

    Raises:
        OSError: If log directory creation fails (treated as fatal)
        FileNotFoundError: If log file cannot be opened (treated as fatal)
    """
    try:
        service.log_file.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise OSError(
            f"Failed to create log directory {service.log_file.parent}: {e}"
        ) from e

    try:
        f = open(service.log_file, "ab", buffering=0)
    except OSError as e:
        raise OSError(f"Failed to open log file {service.log_file}: {e}") from e

    return subprocess.Popen[str](
        service.cmd,
        cwd=service.cwd,
        env=service.env,
        stdout=f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def is_server_healthy(url: str, timeout: float = 1) -> bool:
    """Check if a server is responding at the health endpoint.

    Args:
        url: URL to check (e.g., 'http://localhost:8010')
        timeout: Request timeout in seconds

    Returns:
        True if server responds, False otherwise
    """
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code < 500
    except (requests.RequestException, OSError):
        return False


def stop_process(
    proc: subprocess.Popen[str] | None,
    name: str = "Process",
    timeout: int = 5,
    health_url: str | None = None,
) -> bool:
    """Stop a process gracefully with timeout and health check.

    Args:
        proc: Process to stop
        name: Name of the process for logging
        timeout: Seconds to wait before force killing
        health_url: Optional health check URL to verify shutdown

    Returns:
        True if process stopped gracefully, False if force killed
    """
    if not proc or proc.poll() is not None:
        # Process not running
        if health_url:
            logger.info(f"{name} is not running")
        return True

    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except OSError:
        # Process group might already be gone
        return proc.poll() is not None

    # Wait for graceful shutdown
    start = time.time()
    while time.time() - start < timeout:
        if proc.poll() is not None:
            # Process terminated
            if health_url and is_server_healthy(health_url):
                logger.warning(f"{name}: Attempt to stop gracefully failed")
            else:
                logger.info(f"{name} stopped successfully")
            return True
        time.sleep(0.1)

    # Force kill if still running
    logger.warning(f"{name}: Force kill")
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        pass

    try:
        proc.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass

    # Verify it's gone
    if health_url:
        if is_server_healthy(health_url):
            logger.error(f"{name} force kill failed, Stop {name} manually")
        else:
            logger.info(f"{name} force killed successfully")

    return False


def stop_all_processes(processes: Processes, config: Config | None = None):
    """Stop all running processes.

    Shutdown order:
    1. Workers (depend on compute and auth)
    2. Store (depends on compute and auth)
    3. Compute (depends on auth)
    4. Auth (no dependencies)

    Args:
        processes: Processes object containing all running services
        config: Optional config object with URLs for health checks
    """
    logger.info("Shutting down services")

    # Stop workers first (no health check for workers)
    for i, proc in enumerate(processes.workers):
        logger.info(f"Stopping worker {i + 1}/{len(processes.workers)}...")
        stop_process(proc, f"worker-{i}")

    # Stop store
    if processes.store:
        logger.info("Stopping store...")
        health_url = config.store_url if config else None
        stop_process(processes.store, "store", health_url=health_url)

    # Stop compute
    if processes.compute:
        logger.info("Stopping compute...")
        health_url = config.compute_url if config else None
        stop_process(processes.compute, "compute", health_url=health_url)

    # Stop auth
    if processes.auth:
        logger.info("Stopping auth...")
        health_url = config.auth_url if config else None
        stop_process(processes.auth, "auth", health_url=health_url)

    logger.success("All services stopped.")
