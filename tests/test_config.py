from __future__ import annotations

import json
from pathlib import Path

from whylosemoney import config
from whylosemoney.config import Settings


def test_load_default_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)

    settings = config.load_config()

    assert settings == Settings()


def test_save_and_load_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    original = Settings(
        currency="USD",
        date_format="%d/%m/%Y",
        page_size=50,
        default_category="food",
        custom_categories=["crypto", "travel"],
    )

    config.save_config(original)
    loaded = config.load_config()

    assert loaded == original


def test_merge_preserves_existing(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text(json.dumps({"currency": "USD"}), encoding="utf-8")

    settings = config.load_config()

    assert settings.currency == "USD"
    assert settings.date_format == "%Y-%m-%d"
    assert settings.page_size == 20
    assert settings.default_category == "other"
    assert settings.custom_categories == []


def test_update_config(tmp_path: Path, monkeypatch) -> None:
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    config.save_config(Settings(currency="USD", page_size=10))

    updated = config.update_config(page_size=100)

    assert updated.currency == "USD"
    assert updated.page_size == 100
    assert updated.date_format == "%Y-%m-%d"
    assert updated.default_category == "other"
