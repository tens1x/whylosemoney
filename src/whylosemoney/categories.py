"""Expense category helpers."""

from __future__ import annotations

from whylosemoney.config import load_config, update_config
from whylosemoney.exceptions import CategoryError

DEFAULT_CATEGORIES: tuple[str, ...] = (
    "food",
    "transport",
    "housing",
    "entertainment",
    "shopping",
    "health",
    "education",
    "other",
)


def _normalize(category: str) -> str:
    """Normalize a category for stable validation and storage."""
    return category.strip().lower()


def validate_category(category: str) -> bool:
    """Return whether a category is known."""
    normalized = _normalize(category)
    config = load_config()
    return normalized in DEFAULT_CATEGORIES or normalized in config.custom_categories


def add_custom_category(category: str) -> str:
    """Persist a custom category and return its normalized value."""
    normalized = _normalize(category)
    if not normalized:
        raise CategoryError("Category must not be empty.")

    categories = set(load_config().custom_categories)
    if normalized not in DEFAULT_CATEGORIES:
        categories.add(normalized)
        update_config(custom_categories=sorted(categories))
    return normalized


def get_all_categories() -> list[str]:
    """Return all built-in and custom categories in sorted order."""
    custom_categories = set(load_config().custom_categories)
    return sorted(set(DEFAULT_CATEGORIES) | custom_categories)
