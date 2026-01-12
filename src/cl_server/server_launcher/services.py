from pathlib import Path

from pydantic import BaseModel

from .config import Config


class ServiceArgs(BaseModel):
    cmd: list[str]
    cwd: Path
    env: dict[str, str]
    log_file: Path


class Services(BaseModel):
    auth: ServiceArgs
    store: ServiceArgs
    compute: ServiceArgs
    workers: list[ServiceArgs]


def build_services(cfg: Config, env: dict[str, str]) -> Services:
    workers: list[ServiceArgs] = []
    for i, worker_cfg in enumerate(cfg.workers):
        workers.append(
            ServiceArgs(
                cmd=[
                    "uv",
                    "run",
                    "compute-worker",
                    "--worker-id",
                    worker_cfg.id,
                    "--port",
                    str(cfg.compute.port),
                    "--tasks",
                    ",".join(worker_cfg.tasks),
                ],
                cwd=worker_cfg.dir,
                env=env,
                log_file=cfg.log_dir / f"worker-{i}.log",
            )
        )

    return Services(
        auth=ServiceArgs(
            cmd=["uv", "run", "auth-server", "--port", str(cfg.auth.port)],
            cwd=cfg.auth.dir,
            env=env,
            log_file=cfg.log_dir / "auth.log",
        ),
        store=ServiceArgs(
            cmd=[
                "uv",
                "run",
                "store",
                "--port",
                str(cfg.store.port),
                "--auth-url",
                cfg.auth_url,
                "--compute-url",
                cfg.compute_url,
                "--compute-username",
                "admin",
                "--compute-password",
                "admin",
            ],
            cwd=cfg.store.dir,
            env=env,
            log_file=cfg.log_dir / "store.log",
        ),
        compute=ServiceArgs(
            cmd=[
                "uv",
                "run",
                "compute-server",
                "--port",
                str(cfg.compute.port),
            ],
            cwd=cfg.compute.dir,
            env=env,
            log_file=cfg.log_dir / "compute.log",
        ),
        workers=workers,
    )
