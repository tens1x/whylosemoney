"""Expense analysis helpers."""

from __future__ import annotations

from collections import defaultdict
from typing import Sequence

from whylosemoney.models import Expense


def total_by_category(expenses: Sequence[Expense]) -> dict[str, float]:
    """Return total spend grouped by category."""
    totals: dict[str, float] = defaultdict(float)
    for expense in expenses:
        totals[expense.category] += expense.amount
    return dict(sorted(totals.items()))


def top_expenses(expenses: Sequence[Expense], n: int = 5) -> list[Expense]:
    """Return the largest ``n`` expenses sorted from highest to lowest amount."""
    return sorted(expenses, key=lambda expense: expense.amount, reverse=True)[:n]


def daily_summary(expenses: Sequence[Expense]) -> dict[str, float]:
    """Return total spend grouped by day."""
    totals: dict[str, float] = defaultdict(float)
    for expense in expenses:
        totals[expense.date.date().isoformat()] += expense.amount
    return dict(sorted(totals.items()))


def weekly_summary(expenses: Sequence[Expense]) -> dict[str, float]:
    """Return total spend grouped by ISO week."""
    totals: dict[str, float] = defaultdict(float)
    for expense in expenses:
        iso_year, iso_week, _ = expense.date.isocalendar()
        totals[f"{iso_year}-W{iso_week:02d}"] += expense.amount
    return dict(sorted(totals.items()))


def monthly_summary(expenses: Sequence[Expense]) -> dict[str, float]:
    """Return total spend grouped by month."""
    totals: dict[str, float] = defaultdict(float)
    for expense in expenses:
        totals[expense.date.strftime("%Y-%m")] += expense.amount
    return dict(sorted(totals.items()))


def percentage_breakdown(expenses: Sequence[Expense]) -> dict[str, float]:
    """Return category percentages for the provided expenses."""
    totals = total_by_category(expenses)
    overall = sum(totals.values())
    if overall == 0:
        return {}
    return {
        category: round((amount / overall) * 100, 2)
        for category, amount in totals.items()
    }
