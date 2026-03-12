"""Custom exception hierarchy for WhyLoseMoney."""

from __future__ import annotations


class WhyLoseMoneyError(Exception):
    """Base exception for all WhyLoseMoney errors."""


class StorageError(WhyLoseMoneyError):
    """Raised when storage operations fail."""


class ConfigError(WhyLoseMoneyError):
    """Raised when configuration is invalid or cannot be loaded."""


class ImportError_(WhyLoseMoneyError):
    """Raised when import operations fail."""


class CategoryError(WhyLoseMoneyError):
    """Raised when category validation fails."""
