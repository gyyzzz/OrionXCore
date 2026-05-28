from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ORIONXCORE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OrionXCore"
    host: str = "0.0.0.0"
    port: int = 8080
    model: str = "gpt-4.1-mini"
    api_key: str = ""
    api_base_url: str = "https://api.openai.com/v1"
    system_prompt: str = "You are OrionXCore, a lightweight AI coding agent."
    max_iterations: int = 6
    http_timeout: int = 120

    enable_terminal: bool = True
    terminal_workdir: Path = Field(default_factory=lambda: Path(".").resolve())
    terminal_timeout: int = 30
    allow_risky_commands: bool = False

    enable_database: bool = False
    database_url: str = ""
    database_max_rows: int = 200
    database_query_timeout_seconds: int = 30
    database_allow_mutation: bool = False
    database_allowed_databases: str = ""

    enable_filesystem: bool = False
    filesystem_workdir: Path | None = None
    filesystem_allow_write: bool = True
    filesystem_allow_delete: bool = False
    filesystem_max_read_bytes: int = 1_048_576
    filesystem_max_write_bytes: int = 1_048_576
    filesystem_max_list_entries: int = 500


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
