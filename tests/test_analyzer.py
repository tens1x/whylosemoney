from __future__ import annotations

from datetime import datetime

import pytest

from whylosemoney.analyzer import (
    daily_summary,
    monthly_summary,
    percentage_breakdown,
    top_expenses,
    total_by_category,
    weekly_summary,
)
from whylosemoney.models import Expense


def _sample_expenses() -> list[Expense]:
    return [
        Expense(amount=10, category="food", note="a", date=datetime(2024, 1, 1, 9, 0)),
        Expense(amount=25, category="transport", note="b", date=datetime(2024, 1, 2, 10, 0)),
        Expense(amount=15, category="food", note="c", date=datetime(2024, 1, 8, 11, 0)),
        Expense(amount=50, category="shopping", note="d", date=datetime(2024, 2, 1, 18, 0)),
    ]


def test_total_by_category() -> None:
    totals = total_by_category(_sample_expenses())

    assert totals == {"food": 25.0, "shopping": 50.0, "transport": 25.0}


def test_top_expenses() -> None:
    expenses = top_expenses(_sample_expenses(), n=2)

    assert [expense.amount for expense in expenses] == [50.0, 25.0]


def test_daily_summary() -> None:
    summary = daily_summary(_sample_expenses())

    assert summary == {
        "2024-01-01": 10.0,
        "2024-01-02": 25.0,
        "2024-01-08": 15.0,
        "2024-02-01": 50.0,
    }


def test_weekly_summary() -> None:
    summary = weekly_summary(_sample_expenses())

    assert summary == {
        "2024-W01": 35.0,
        "2024-W02": 15.0,
        "2024-W05": 50.0,
    }


def test_monthly_summary() -> None:
    summary = monthly_summary(_sample_expenses())

    assert summary == {"2024-01": 50.0, "2024-02": 50.0}


def test_percentage_breakdown() -> None:
    breakdown = percentage_breakdown(_sample_expenses())

    assert breakdown["food"] == pytest.approx(25.0)
    assert breakdown["transport"] == pytest.approx(25.0)
    assert breakdown["shopping"] == pytest.approx(50.0)
