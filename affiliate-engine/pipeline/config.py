"""Configuration management using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SITE_CONTENT_DIR = PROJECT_ROOT / "site" / "src" / "content" / "articles"


class AmazonConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AMAZON_")

    access_key: str = ""
    secret_key: str = ""
    partner_tag: str = ""
    marketplace: str = "www.amazon.co.jp"
    region: str = "us-west-2"

    @property
    def is_configured(self) -> bool:
        return bool(self.access_key and self.secret_key and self.partner_tag)


class RakutenConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAKUTEN_")

    app_id: str = ""
    affiliate_id: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.app_id and self.affiliate_id)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str = ""

    # Affiliate
    amazon: AmazonConfig = Field(default_factory=AmazonConfig)
    rakuten: RakutenConfig = Field(default_factory=RakutenConfig)

    # Content
    content_locale: str = "ja_JP"
    daily_article_limit: int = 3

    # Site
    site_url: str = "https://example.github.io/affiliate-engine"
    site_title: str = "スマート比較ナビ"

    # Paths
    data_dir: Path = DATA_DIR
    site_content_dir: Path = SITE_CONTENT_DIR


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached singleton settings instance."""
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
    return _settings
