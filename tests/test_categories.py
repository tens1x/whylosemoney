from __future__ import annotations

from pathlib import Path

import pytest

from whylosemoney import config
from whylosemoney.categories import (
    DEFAULT_CATEGORIES,
    add_custom_category,
    get_all_categories,
    validate_category,
)
from whylosemoney.exceptions import CategoryError


def test_validate_default_category(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    assert validate_category("food") is True


def test_validate_unknown_category(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    assert validate_category("xyz") is False


def test_add_and_validate_custom(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    add_custom_category("crypto")

    assert validate_category("crypto") is True


def test_get_all_categories(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    add_custom_category("crypto")

    categories = get_all_categories()

    assert categories == sorted([*DEFAULT_CATEGORIES, "crypto"])


def test_add_empty_category_raises(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    with pytest.raises(CategoryError):
        add_custom_category("")
