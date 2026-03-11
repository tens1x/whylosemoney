from __future__ import annotations

from datetime import datetime
from pathlib import Path

from whylosemoney.models import Expense
from whylosemoney import storage


def test_storage_crud(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "data.json"
    monkeypatch.setattr(storage, "DATA_FILE", data_file)

    expense = Expense(
        amount=23.4,
        category="food",
        note="dinner",
        date=datetime(2026, 3, 1, 18, 0),
    )
    storage.add_expense(expense)

    fetched = storage.get_expense(expense.id)

    assert fetched is not None
    assert fetched.id == expense.id
    assert fetched.note == "dinner"

    items = storage.list_expenses()
    assert len(items) == 1
    assert items[0].id == expense.id

    assert storage.delete_expense(expense.id) is True
    assert storage.get_expense(expense.id) is None


def test_list_expenses_with_date_range(tmp_path: Path, monkeypatch) -> None:
    data_file = tmp_path / "data.json"
    monkeypatch.setattr(storage, "DATA_FILE", data_file)

    early = Expense(amount=10, category="transport", date=datetime(2026, 3, 1, 8, 0))
    middle = Expense(amount=20, category="food", date=datetime(2026, 3, 5, 12, 0))
    late = Expense(amount=30, category="shopping", date=datetime(2026, 3, 10, 20, 0))

    storage.add_expense(early)
    storage.add_expense(middle)
    storage.add_expense(late)

    items = storage.list_expenses(
        date_from=datetime(2026, 3, 2),
        date_to=datetime(2026, 3, 9, 23, 59, 59),
    )

    assert [item.id for item in items] == [middle.id]
