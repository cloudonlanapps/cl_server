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
    workers: list[ServiceConfig]


def build_services(cfg, env) -> Services:
    workers = []
    for i, worker_cfg in enumerate(cfg.workers):
        workers.append(
            ServiceConfig(
                cmd=[
                    "uv",
                    "run",
                    "compute-worker",
                    "--worker-id",
                    worker_cfg.id,
                    "--port",
                    str(cfg.compute_port),
                    "--tasks",
                    ",".join(worker_cfg.tasks),
                ],
                cwd=worker_cfg.dir,
                env=env,
                log_file=cfg.log_dir / f"worker-{i}.log",
            )
        )

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
                *([] if cfg.compute_guest_mode == "off" else ["--guest-mode"]),
            ],
            cwd=cfg.compute_dir,
            env=env,
            log_file=cfg.log_dir / "compute.log",
        ),
        workers=workers,
    )
