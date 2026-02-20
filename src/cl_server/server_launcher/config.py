from pathlib import Path

from pydantic import BaseModel, field_validator


class ServiceConfig(BaseModel):
    """Auth service configuration."""

    dir: Path
    port: int


class WorkerConfig(BaseModel):
    """Worker service configuration."""

    dir: Path
    id: str
    tasks: list[str]
    poll_interval: float = 1.0


class BroadcasterConfig(BaseModel):
    """Broadcaster service configuration."""
    
    interval: float = 5.0
    service_name: str = "server100@cloudonlapapps"
    service_type: str = "_http._tcp"
    txt_record: str = "desc=CL Image Repo Service"



class Config(BaseModel):
    """Server launcher configuration loaded from JSON."""

    data_dir: Path
    log_dir: Path

    auth: ServiceConfig

    @field_validator("data_dir", "log_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> str:
        """Expand ~ in paths."""
        return str(Path(v).expanduser())
    store: ServiceConfig
    compute: ServiceConfig
    workers: list[WorkerConfig]
    broadcaster: BroadcasterConfig = BroadcasterConfig()

    mqtt_url: str = "mqtt://localhost:1883"

    # model_config = {"arbitrary_types_allowed": True}

    @property
    def auth_url(self) -> str:
        return f"http://localhost:{self.auth.port}"

    @property
    def store_url(self) -> str:
        return f"http://localhost:{self.store.port}"

    @property
    def compute_url(self) -> str:
        return f"http://localhost:{self.compute.port}"


def load_config(path: Path | str) -> Config:
    """Load configuration from a JSON file.

    Args:
        path: Path to the JSON config file

    Returns:
        Config: Parsed configuration object

    Raises:
        FileNotFoundError: If the config file doesn't exist
        json.JSONDecodeError: If the JSON is invalid
        ValueError: If the configuration is invalid
    """
    path = Path(path) if isinstance(path, str) else path

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    return Config.model_validate_json(path.read_text())
