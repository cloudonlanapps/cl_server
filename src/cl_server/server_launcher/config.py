from pathlib import Path

from pydantic import BaseModel, field_validator


class AuthConfig(BaseModel):
    """Auth service configuration."""

    dir: Path
    port: int


class StoreConfig(BaseModel):
    """Store service configuration."""

    dir: Path
    port: int
    guest_mode: str

    @field_validator("guest_mode")
    @classmethod
    def validate_guest_mode(cls, v: str) -> str:
        """Validate guest_mode is 'on' or 'off'."""
        if v not in ("on", "off"):
            raise ValueError("guest_mode must be 'on' or 'off'")
        return v


class ComputeConfig(BaseModel):
    """Compute service configuration."""

    dir: Path
    port: int
    guest_mode: str

    @field_validator("guest_mode")
    @classmethod
    def validate_guest_mode(cls, v: str) -> str:
        """Validate guest_mode is 'on' or 'off'."""
        if v not in ("on", "off"):
            raise ValueError("guest_mode must be 'on' or 'off'")
        return v


class WorkerConfig(BaseModel):
    """Worker service configuration."""

    id: str
    dir: Path
    tasks: list[str]


class Config(BaseModel):
    """Server launcher configuration loaded from JSON."""

    data_dir: Path
    log_dir: Path

    auth: AuthConfig
    store: StoreConfig
    compute: ComputeConfig
    workers: list[WorkerConfig]

    model_config = {"arbitrary_types_allowed": True}

    # Convenience properties for backwards compatibility
    @property
    def auth_dir(self) -> Path:
        return self.auth.dir

    @property
    def auth_port(self) -> int:
        return self.auth.port

    @property
    def store_dir(self) -> Path:
        return self.store.dir

    @property
    def store_port(self) -> int:
        return self.store.port

    @property
    def store_guest_mode(self) -> str:
        return self.store.guest_mode

    @property
    def compute_dir(self) -> Path:
        return self.compute.dir

    @property
    def compute_port(self) -> int:
        return self.compute.port

    @property
    def compute_guest_mode(self) -> str:
        return self.compute.guest_mode

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
