"""Persistent configuration helpers for WhyLoseMoney."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from whylosemoney.exceptions import ConfigError

CONFIG_FILE: Path = Path.home() / ".whylosemoney" / "config.json"


class Settings(BaseModel):
    """Application settings stored in the user configuration file."""

    currency: str = "CNY"
    date_format: str = "%Y-%m-%d"
    page_size: int = 20
    default_category: str = "other"
    custom_categories: list[str] = Field(default_factory=list)


def load_config() -> Settings:
    """Load configuration from disk and merge it with default values."""
    defaults = Settings().model_dump()
    if not CONFIG_FILE.exists():
        return Settings.model_validate(defaults)

    try:
        raw_data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"配置加载失败：{exc}") from exc

    if not isinstance(raw_data, dict):
        raise ConfigError("配置加载失败：配置根节点必须是 JSON 对象。")

    merged = {**defaults, **raw_data}
    try:
        return Settings.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"配置验证失败：{exc}") from exc


def save_config(settings: Settings) -> None:
    """Persist validated settings to disk."""
    try:
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(settings.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise ConfigError(f"配置保存失败：{exc}") from exc


def update_config(**overrides: object) -> Settings:
    """Apply overrides to the current settings, persist them, and return the result."""
    current = load_config()
    merged = {**current.model_dump(), **overrides}
    try:
        updated = Settings.model_validate(merged)
    except ValidationError as exc:
        raise ConfigError(f"配置验证失败：{exc}") from exc
    save_config(updated)
    return updated
