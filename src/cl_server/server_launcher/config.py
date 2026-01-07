from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Config:
    auth_dir: Path
    store_dir: Path
    compute_dir: Path
    worker_dir: Path

    auth_port: int
    store_port: int
    compute_port: int

    data_dir: Path
    log_dir: Path

    compute_auth_required: bool
    store_guest_mode: str

    worker_id: str
    tasks: list[str]

    @property
    def auth_url(self) -> str:
        return f"http://localhost:{self.auth_port}"

    @property
    def store_url(self) -> str:
        return f"http://localhost:{self.store_port}"

    @property
    def compute_url(self) -> str:
        return f"http://localhost:{self.compute_port}"


def load_config(path: Path | str) -> Config:
    path = Path(path) if isinstance(path, str) else path
    raw = tomllib.loads(path.read_text())

    guest_mode = raw["store"]["guest_mode"]
    if guest_mode not in ("on", "off"):
        raise ValueError("store.guest_mode must be 'on' or 'off'")

    return Config(
        auth_dir=Path(raw["paths"]["auth_dir"]),
        store_dir=Path(raw["paths"]["store_dir"]),
        compute_dir=Path(raw["paths"]["compute_dir"]),
        worker_dir=Path(raw["paths"]["worker_dir"]),
        auth_port=raw["ports"]["auth"],
        store_port=raw["ports"]["store"],
        compute_port=raw["ports"]["compute"],
        data_dir=Path(raw["data"]["dir"]),
        log_dir=Path(raw["data"]["log_dir"]),
        compute_auth_required=raw["compute"]["auth_required"],
        store_guest_mode=guest_mode,
        worker_id=raw["worker"]["id"],
        tasks=raw["worker"]["tasks"],
    )
