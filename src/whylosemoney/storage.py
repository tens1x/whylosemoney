"""JSON file-based storage helpers."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import fcntl

from whylosemoney.models import Expense

DATA_FILE: Path = Path.home() / ".whylosemoney" / "data.json"


def _ensure_data_file() -> None:
    """Create the storage file if it does not already exist."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"expenses": []}, indent=2), encoding="utf-8")


@contextmanager
def _locked_file() -> Iterator[object]:
    """Open the JSON file with an exclusive lock for safe read/write cycles."""
    _ensure_data_file()
    with DATA_FILE.open("r+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield handle
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_records(handle: object) -> dict[str, list[dict[str, object]]]:
    """Load JSON records from an already locked file handle."""
    handle.seek(0)
    raw_content = handle.read()
    if not raw_content.strip():
        return {"expenses": []}
    data = json.loads(raw_content)
    if not isinstance(data, dict):
        raise ValueError("Storage file is malformed.")
    expenses = data.get("expenses", [])
    if not isinstance(expenses, list):
        raise ValueError("Storage file is malformed.")
    return {"expenses": expenses}


def _write_records(handle: object, data: dict[str, list[dict[str, object]]]) -> None:
    """Persist JSON records to an already locked file handle."""
    handle.seek(0)
    json.dump(data, handle, indent=2)
    handle.truncate()
    handle.flush()


def add_expense(expense: Expense) -> Expense:
    """Persist a new expense and return it."""
    with _locked_file() as handle:
        data = _load_records(handle)
        data["expenses"].append(expense.model_dump(mode="json"))
        _write_records(handle, data)
    return expense


def get_expense(expense_id: str) -> Expense | None:
    """Return a stored expense by ID, or ``None`` when it does not exist."""
    with _locked_file() as handle:
        data = _load_records(handle)
    for item in data["expenses"]:
        if item.get("id") == expense_id:
            return Expense.model_validate(item)
    return None


def list_expenses(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[Expense]:
    """List expenses, optionally filtered by an inclusive datetime range."""
    with _locked_file() as handle:
        data = _load_records(handle)
    expenses = [Expense.model_validate(item) for item in data["expenses"]]
    filtered: list[Expense] = []
    for expense in expenses:
        if date_from is not None and expense.date < date_from:
            continue
        if date_to is not None and expense.date > date_to:
            continue
        filtered.append(expense)
    return sorted(filtered, key=lambda item: item.date, reverse=True)


def delete_expense(expense_id: str) -> bool:
    """Delete an expense by ID and report whether anything was removed."""
    with _locked_file() as handle:
        data = _load_records(handle)
        original_count = len(data["expenses"])
        data["expenses"] = [
            item for item in data["expenses"] if item.get("id") != expense_id
        ]
        deleted = len(data["expenses"]) != original_count
        if deleted:
            _write_records(handle, data)
    return deleted
