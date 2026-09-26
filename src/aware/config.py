"""
Aware configuration management.

All settings can be overridden via environment variables with the AWARE_ prefix.
Example: AWARE_DATABASE_URL=postgresql://...
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="AWARE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "Aware"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "127.0.0.1"
    port: int = 8000
    workers: int = 1

    # Database
    database_url: str = Field(
        default="sqlite+aiosqlite:///./aware.db",
        description="Database connection URL. Use postgresql+asyncpg:// for production.",
    )

    # Authentication
    secret_key: SecretStr = Field(
        default=SecretStr("CHANGE-ME-IN-PRODUCTION-use-openssl-rand-hex-32"),
        description="Secret key for JWT signing. Generate with: openssl rand -hex 32",
    )
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    algorithm: str = "HS256"

    # Location tracking
    location_update_throttle_seconds: int = Field(
        default=10,
        description="Minimum seconds between location updates from same device",
    )
    location_history_retention_days: int = Field(
        default=30,
        description="Days to retain location history. 0 = forever",
    )
    default_location_fuzz_meters: float = Field(
        default=0,
        description="Default location fuzzing radius in meters. 0 = exact",
    )

    # External APIs
    ip_geolocation_api: str = "https://ipwho.is"
    ip_geolocation_timeout_seconds: float = 10.0
    username_check_timeout_seconds: float = 5.0
    username_check_concurrency: int = 10

    # Paths
    data_dir: Path = Field(
        default=Path.home() / ".aware",
        description="Directory for local data storage",
    )

    @field_validator("data_dir", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Expand ~ and resolve path."""
        return Path(v).expanduser().resolve()

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience alias
settings = get_settings()
