import subprocess
import os
import signal
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
from .services import ServiceConfig


class Processes(BaseModel):
    model_config = {"arbitrary_types_allowed": True}
    
    auth: Optional[subprocess.Popen] = None
    store: Optional[subprocess.Popen] = None
    compute: Optional[subprocess.Popen] = None
    worker: Optional[subprocess.Popen] = None


def start_process(service: ServiceConfig) -> subprocess.Popen:
    service.log_file.parent.mkdir(parents=True, exist_ok=True)
    f = open(service.log_file, "ab", buffering=0)

    return subprocess.Popen(
        service.cmd,
        cwd=service.cwd,
        env=service.env,
        stdout=f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )


def stop_process(proc: Optional[subprocess.Popen]):
    if proc and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)


def stop_all_processes(processes: Processes):
    """Stop all running processes in the container."""
    for proc in [processes.auth, processes.store, processes.compute, processes.worker]:
        stop_process(proc)
