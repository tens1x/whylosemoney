from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from whylosemoney.models import Expense
from whylosemoney import storage
from whylosemoney.exceptions import StorageError


def _patch_storage_paths(tmp_path: Path, monkeypatch) -> Path:
    data_file = tmp_path / "data.json"
    monkeypatch.setattr(storage, "DATA_FILE", data_file)
    monkeypatch.setattr(storage, "LOCK_FILE", tmp_path / "data.json.lock")
    monkeypatch.setattr(storage, "HISTORY_FILE", tmp_path / "history.jsonl")
    return data_file


def test_storage_crud(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)

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
    _patch_storage_paths(tmp_path, monkeypatch)

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


def test_malformed_storage_raises_error(tmp_path: Path, monkeypatch) -> None:
    data_file = _patch_storage_paths(tmp_path, monkeypatch)
    data_file.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(StorageError):
        storage.list_expenses()


def test_history_logging(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    expense = Expense(amount=8.5, category="food", date=datetime(2026, 3, 2, 9, 0))

    storage.add_expense(expense)
    history = storage.get_history()

    assert len(history) == 1
    assert history[0]["operation"] == "add"
    assert history[0]["detail"] == {
        "id": expense.id,
        "amount": expense.amount,
        "category": expense.category,
    }


def test_get_history(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    first = Expense(amount=5, category="food", date=datetime(2026, 3, 1, 9, 0))
    second = Expense(amount=6, category="shopping", date=datetime(2026, 3, 2, 10, 0))

    storage.add_expense(first)
    storage.add_expense(second)
    history = storage.get_history(limit=2)

    assert len(history) == 2
    assert [entry["detail"]["id"] for entry in history] == [first.id, second.id]
