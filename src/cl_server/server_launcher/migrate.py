"""Database migration utilities for services."""

import subprocess
from pathlib import Path
from loguru import logger


def run_migration(service_dir: Path, service_name: str, env: dict[str, str]) -> bool:
    """Run Alembic migrations for a service.

    Args:
        service_dir: Service directory path from config
        service_name: Name of the service (e.g., 'auth', 'store')
        env: Environment variables to pass to the migration command

    Returns:
        True if migration succeeded, False otherwise
    """
    if not service_dir.exists():
        logger.warning(f" Service directory does not exist: {service_dir}")
        return False

    alembic_ini = service_dir / "alembic.ini"
    if not alembic_ini.exists():
        logger.warning(f" No alembic.ini found in {service_dir}")
        return False

    logger.info(f" Running migrations for {service_name} at {service_dir}...")

    try:
        result = subprocess.run(
            ["uv", "run", "alembic", "upgrade", "head"],
            cwd=str(service_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            logger.error(f"Migration failed for {service_name}")
            logger.debug(f"STDOUT: {result.stdout}")
            logger.debug(f"STDERR: {result.stderr}")
            return False

        logger.success(f" Migration completed for {service_name}")
        return True

    except subprocess.TimeoutExpired:
        logger.error(f"Migration timed out for {service_name}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during migration for {service_name}: {e}")
        return False


def migrate_auth(auth_dir: Path, env: dict[str, str]) -> bool:
    """Run auth service migrations.

    Args:
        auth_dir: Auth service directory from config
        env: Environment variables to pass to the migration command

    Returns:
        True if migration succeeded, False otherwise
    """
    return run_migration(auth_dir, "auth", env)


def migrate_store(store_dir: Path, env: dict[str, str]) -> bool:
    """Run store service migrations.

    Args:
        store_dir: Store service directory from config
        env: Environment variables to pass to the migration command

    Returns:
        True if migration succeeded, False otherwise
    """
    return run_migration(store_dir, "store", env)


def migrate_compute(compute_dir: Path, env: dict[str, str]) -> bool:
    """Run compute service migrations.

    Args:
        compute_dir: Compute service directory from config
        env: Environment variables to pass to the migration command

    Returns:
        True if migration succeeded, False otherwise
    """
    return run_migration(compute_dir, "compute", env)
