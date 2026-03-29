"""Application settings with Pydantic, loaded from env vars and .env files."""

from __future__ import annotations

import functools
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class PortalSettings(BaseSettings):
    """Central configuration for the OpsPortal shell application."""

    model_config = SettingsConfigDict(
        env_prefix="OPSPORTAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Server ---
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    log_level: str = "info"

    # --- Paths ---
    manifest_path: Path = Field(
        default=Path("opsportal.yaml"),
        description="Path to the YAML tool manifest file",
    )
    artifact_dir: Path = Field(
        default=Path("artifacts"),
        description="Root directory for generated artifacts",
    )
    work_dir: Path = Field(
        default=Path("work"),
        description="Working/temp directory for portal operations",
    )
    tools_work_dir: Path = Field(
        default=Path(""),
        description="Per-tool work directory for configs/data (default: work_dir/tools)",
    )
    tools_base_dir: Path = Field(
        default=Path(".."),
        description="Base directory to resolve relative tool repo paths (legacy/dev)",
    )

    # --- Limits ---
    process_startup_timeout: int = Field(default=30, ge=5, le=120)
    cli_task_timeout: int = Field(default=300, ge=10, le=3600)
    log_buffer_size: int = Field(default=5000, ge=100, le=50000)
    health_check_interval: int = Field(default=30, ge=5, le=300)

    # --- Authentication ---
    auth_enabled: bool = Field(default=False, description="Enable basic authentication")
    auth_username: str = Field(default="admin", description="Basic auth username")
    auth_password: str = Field(
        default="",
        description="Basic auth password (required if auth_enabled)",
    )

    # --- Metrics & Monitoring ---
    metrics_enabled: bool = Field(default=True, description="Enable /metrics Prometheus endpoint")
    uptime_data_dir: Path = Field(
        default=Path(""),
        description="Dir for uptime data (default: work_dir/uptime)",
    )

    # --- Notifications ---
    webhook_urls: str = Field(default="", description="Comma-separated webhook URLs for alerts")

    # --- Scheduler ---
    scheduler_enabled: bool = Field(default=True, description="Enable action scheduler")
    scheduler_config_path: Path = Field(
        default=Path(""), description="Scheduler jobs file (default: work_dir/scheduler.json)"
    )

    # --- Hot-reload ---
    manifest_watch: bool = Field(default=True, description="Watch opsportal.yaml for changes")
    manifest_watch_interval: float = Field(default=5.0, ge=1.0, le=60.0)

    # --- Cache ---
    cache_ttl: int = Field(
        default=300,
        ge=30,
        le=3600,
        description="TTL for logo/schema cache (seconds)",
    )

    # --- Operations Overview ---
    ops_overview_enabled: bool = Field(
        default=False,
        description="Enable the Operations Overview dashboard",
    )

    # --- Artifact cleanup ---
    artifact_cleanup_enabled: bool = Field(default=True, description="Auto-cleanup old artifacts")
    artifact_max_age_days: int = Field(default=7, ge=1, le=365)
    artifact_cleanup_interval: int = Field(default=3600, ge=300, le=86400)

    @field_validator("log_level")
    @classmethod
    def _normalise_log_level(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in ("debug", "info", "warning", "error", "critical"):
            msg = f"Invalid log level: {v!r}"
            raise ValueError(msg)
        return v

    @field_validator(
        "manifest_path",
        "artifact_dir",
        "work_dir",
        "tools_base_dir",
        "tools_work_dir",
        "uptime_data_dir",
        "scheduler_config_path",
    )
    @classmethod
    def _resolve_path(cls, v: Path) -> Path:
        return v.resolve() if v != Path("") and not v.is_absolute() else v

    @model_validator(mode="after")
    def _derive_tools_work_dir(self) -> PortalSettings:
        if self.tools_work_dir == Path(""):
            object.__setattr__(self, "tools_work_dir", self.work_dir / "tools")
        if self.uptime_data_dir == Path(""):
            object.__setattr__(self, "uptime_data_dir", self.work_dir / "uptime")
        if self.scheduler_config_path == Path(""):
            object.__setattr__(self, "scheduler_config_path", self.work_dir / "scheduler.json")
        return self


@functools.lru_cache(maxsize=1)
def get_settings() -> PortalSettings:
    """Singleton accessor for portal settings (cached)."""
    return PortalSettings()
