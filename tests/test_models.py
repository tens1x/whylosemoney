from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from whylosemoney.models import Expense


def test_expense_creation() -> None:
    expense = Expense(amount=12.5, category="Food", date=datetime(2026, 3, 11, 9, 30))

    assert expense.id
    assert expense.amount == 12.5
    assert expense.category == "food"
    assert expense.note == ""
    assert expense.created_at is not None


def test_negative_amount_rejected() -> None:
    with pytest.raises(ValidationError):
        Expense(amount=-1.0, category="food", date=datetime(2026, 3, 11))


def test_expense_serialization() -> None:
    expense = Expense(
        amount=88.2,
        category="shopping",
        note="keyboard",
        date=datetime(2026, 3, 10, 20, 15),
    )

    serialized = expense.model_dump(mode="json")

    assert serialized["category"] == "shopping"
    assert serialized["note"] == "keyboard"
    assert serialized["date"] == "2026-03-10T20:15:00"
