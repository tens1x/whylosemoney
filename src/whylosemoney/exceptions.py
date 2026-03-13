"""Custom exception hierarchy for WhyLoseMoney."""

from __future__ import annotations


class WhyLoseMoneyError(Exception):
    """WhyLoseMoney 基础异常。"""


class StorageError(WhyLoseMoneyError):
    """存储操作失败时抛出。"""


class ConfigError(WhyLoseMoneyError):
    """配置无效或无法加载时抛出。"""


class ImportError_(WhyLoseMoneyError):
    """导入操作失败时抛出。"""


class CategoryError(WhyLoseMoneyError):
    """分类校验失败时抛出。"""
