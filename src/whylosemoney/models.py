"""Pydantic data models for WhyLoseMoney."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize datetimes to naive UTC for consistent storage and comparison."""
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class Expense(BaseModel):
    """Represents a single expense entry."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    amount: float
    category: str
    note: str = ""
    date: datetime
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        """Ensure that expense amounts are positive."""
        if value <= 0:
            raise ValueError("Amount must be positive.")
        return value

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        """Ensure that categories are non-empty strings."""
        if not value:
            raise ValueError("Category must not be empty.")
        return value.lower()

    @field_validator("note", mode="before")
    @classmethod
    def validate_note(cls, value: str | None) -> str:
        """Default missing notes to an empty string."""
        if value is None:
            return ""
        return str(value)

    @field_validator("date", "created_at")
    @classmethod
    def normalize_datetime_fields(cls, value: datetime) -> datetime:
        """Normalize stored datetimes for stable comparisons."""
        return _normalize_datetime(value)
