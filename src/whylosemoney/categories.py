"""Expense category helpers."""

from __future__ import annotations

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

_CUSTOM_CATEGORIES: set[str] = set()


def _normalize(category: str) -> str:
    return category.strip().lower()


def validate_category(category: str) -> bool:
    """Return whether a category is known."""
    normalized = _normalize(category)
    return normalized in DEFAULT_CATEGORIES or normalized in _CUSTOM_CATEGORIES


def add_custom_category(category: str) -> str:
    """Register a custom category and return its normalized value."""
    normalized = _normalize(category)
    if not normalized:
        raise ValueError("Category must not be empty.")
    _CUSTOM_CATEGORIES.add(normalized)
    return normalized
