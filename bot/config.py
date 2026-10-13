"""
Configuration management for Telegram Media Bot.
Safely parses and validates environment variables.
"""

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot Credentials
    bot_token: str = Field(..., alias="BOT_TOKEN")
    api_id: int = Field(..., alias="API_ID")
    api_hash: str = Field(..., alias="API_HASH")

    # Owner / Admin IDs
    owner_id: Optional[int] = Field(default=None, alias="OWNER_ID")
    admin_ids_raw: Optional[str] = Field(default=None, alias="ADMIN_IDS")

    # Database
    mongo_uri: Optional[str] = Field(default=None, alias="MONGO_URI")
    mongo_db_name: str = Field(default="media_converter_bot", alias="MONGO_DB_NAME")

    # Host & Handoff Settings
    host_mode: str = Field(default="auto", alias="HOST_MODE")  # 'render', 'colab', 'auto'
    big_file_threshold_mb: int = Field(default=100, alias="BIG_FILE_THRESHOLD_MB")
    port: int = Field(default=10000, alias="PORT")
    repo_url: Optional[str] = Field(default=None, alias="REPO_URL")
    max_concurrent_jobs: int = Field(default=1, alias="MAX_CONCURRENT_JOBS")

    # Computed fields
    @property
    def admin_ids(self) -> List[int]:
        ids = set()
        if self.owner_id:
            ids.add(self.owner_id)
        if self.admin_ids_raw:
            for part in self.admin_ids_raw.split(","):
                part = part.strip()
                if part.isdigit():
                    ids.add(int(part))
        return list(ids)

    @property
    def primary_owner_id(self) -> int:
        if self.owner_id:
            return self.owner_id
        admins = self.admin_ids
        if admins:
            return admins[0]
        return 0

    @property
    def big_file_threshold_bytes(self) -> int:
        return self.big_file_threshold_mb * 1024 * 1024

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids or user_id == self.primary_owner_id


# Global cached settings instance
settings = Settings()
