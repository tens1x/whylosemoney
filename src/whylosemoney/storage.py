"""JSON file-based storage helpers."""

from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Iterator

from filelock import FileLock

from whylosemoney.exceptions import StorageError
from whylosemoney.models import Expense

DATA_FILE: Path = Path.home() / ".whylosemoney" / "data.json"
LOCK_FILE: Path = DATA_FILE.parent / "data.json.lock"
HISTORY_FILE: Path = Path.home() / ".whylosemoney" / "history.jsonl"


def _ensure_data_file() -> None:
    """Create the storage file if it does not already exist."""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"expenses": []}, indent=2), encoding="utf-8")


@contextmanager
def _locked_file() -> Iterator[IO[str]]:
    """Open the JSON file with an exclusive lock for safe read/write cycles."""
    _ensure_data_file()
    lock = FileLock(str(LOCK_FILE), timeout=10)
    with lock:
        with DATA_FILE.open("r+", encoding="utf-8") as handle:
            yield handle


def _load_records(handle: IO[str]) -> dict[str, list[dict[str, object]]]:
    """Load JSON records from an already locked file handle."""
    try:
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
    except (json.JSONDecodeError, ValueError) as exc:
        raise StorageError(f"Failed to parse storage file: {exc}") from exc


def _write_records(handle: IO[str], data: dict[str, list[dict[str, object]]]) -> None:
    """Persist JSON records to an already locked file handle."""
    handle.seek(0)
    json.dump(data, handle, indent=2)
    handle.truncate()
    handle.flush()


def _log_operation(operation: str, detail: dict[str, object]) -> None:
    """Append an audit log entry without interrupting user operations on failure."""
    try:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "detail": detail,
        }
        with HISTORY_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except OSError:
        pass


def add_expense(expense: Expense) -> Expense:
    """Persist a new expense and return it."""
    with _locked_file() as handle:
        data = _load_records(handle)
        data["expenses"].append(expense.model_dump(mode="json"))
        _write_records(handle, data)
    _log_operation(
        "add",
        {"id": expense.id, "amount": expense.amount, "category": expense.category},
    )
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
    if deleted:
        _log_operation("delete", {"id": expense_id})
    return deleted


def get_history(limit: int = 50) -> list[dict[str, object]]:
    """Return the most recent audit log entries."""
    if not HISTORY_FILE.exists():
        return []

    lines = HISTORY_FILE.read_text(encoding="utf-8").strip().splitlines()
    entries: list[dict[str, object]] = []
    for line in lines[-limit:]:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict):
            entries.append(entry)
    return entries
