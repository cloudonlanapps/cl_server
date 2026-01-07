from pathlib import Path
from pydantic import BaseModel


class ServiceConfig(BaseModel):
    cmd: list[str]
    cwd: Path
    env: dict[str, str]
    log_file: Path


class Services(BaseModel):
    auth: ServiceConfig
    store: ServiceConfig
    compute: ServiceConfig
    worker: ServiceConfig


def build_services(cfg, env) -> Services:
    return Services(
        auth=ServiceConfig(
            cmd=["uv", "run", "auth-server", "--port", str(cfg.auth_port)],
            cwd=cfg.auth_dir,
            env=env,
            log_file=cfg.log_dir / "auth.log",
        ),
        store=ServiceConfig(
            cmd=["uv", "run", "store", "--port", str(cfg.store_port)],
            cwd=cfg.store_dir,
            env=env,
            log_file=cfg.log_dir / "store.log",
        ),
        compute=ServiceConfig(
            cmd=[
                "uv",
                "run",
                "compute-server",
                "--port",
                str(cfg.compute_port),
                *([] if cfg.compute_auth_required else ["--no-auth"]),
            ],
            cwd=cfg.compute_dir,
            env=env,
            log_file=cfg.log_dir / "compute.log",
        ),
        worker=ServiceConfig(
            cmd=[
                "uv",
                "run",
                "compute-worker",
                "--worker-id",
                cfg.worker_id,
                "--port",
                str(cfg.compute_port),
                "--tasks",
                ",".join(cfg.tasks),
            ],
            cwd=cfg.worker_dir,
            env=env,
            log_file=cfg.log_dir / "worker.log",
        ),
    )
