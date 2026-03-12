"""CSV batch import with checkpoint resume support."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from whylosemoney.exceptions import ImportError_, WhyLoseMoneyError
from whylosemoney.models import Expense
from whylosemoney.storage import add_expense, list_expenses

CHECKPOINT_FILE: Path = Path.home() / ".whylosemoney" / "import_checkpoint.json"
_REQUIRED_COLUMNS = {"amount", "category", "date"}


@dataclass
class ImportResult:
    """Summary of a batch import operation."""

    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list[tuple[int, str]] = field(default_factory=list)


def import_csv(file_path: Path, *, resume: bool = False) -> ImportResult:
    """Import expenses from a CSV file and optionally resume from a checkpoint."""
    csv_path = Path(file_path)
    if not csv_path.exists() or not csv_path.is_file():
        raise ImportError_(f"CSV file not found: {csv_path}")

    start_row = _load_checkpoint(csv_path) if resume else None
    existing_keys = {
        _expense_key(expense)
        for expense in list_expenses()
    }
    result = ImportResult()

    try:
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            _validate_columns(reader.fieldnames)

            for row_number, raw_row in enumerate(reader, start=2):
                if start_row is not None and row_number <= start_row:
                    continue

                try:
                    expense = _expense_from_row(raw_row)
                    expense_key = _expense_key(expense)
                    if expense_key in existing_keys:
                        result.skipped += 1
                    else:
                        add_expense(expense)
                        existing_keys.add(expense_key)
                        result.succeeded += 1
                except (
                    KeyError,
                    TypeError,
                    ValueError,
                    ValidationError,
                    WhyLoseMoneyError,
                ) as exc:
                    result.failed += 1
                    result.errors.append((row_number, str(exc)))

                if row_number % 50 == 0:
                    _save_checkpoint(csv_path, row_number)
    except OSError as exc:
        raise ImportError_(f"Failed to read CSV file: {exc}") from exc
    except csv.Error as exc:
        raise ImportError_(f"Failed to parse CSV file: {exc}") from exc

    _clear_checkpoint()
    return result


def _save_checkpoint(file_path: Path, last_row: int) -> None:
    """Persist the current CSV import position to disk."""
    payload = {"file": str(file_path), "last_row": last_row}
    try:
        CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise ImportError_(f"Failed to save checkpoint: {exc}") from exc


def _load_checkpoint(file_path: Path) -> Optional[int]:
    """Load the checkpoint row for a specific CSV file, if one exists."""
    if not CHECKPOINT_FILE.exists():
        return None

    try:
        payload = json.loads(CHECKPOINT_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None
    if payload.get("file") != str(file_path):
        return None

    last_row = payload.get("last_row")
    if not isinstance(last_row, int):
        return None
    return last_row


def _clear_checkpoint() -> None:
    """Delete any persisted checkpoint file."""
    try:
        if CHECKPOINT_FILE.exists():
            CHECKPOINT_FILE.unlink()
    except OSError as exc:
        raise ImportError_(f"Failed to clear checkpoint: {exc}") from exc


def _validate_columns(fieldnames: Optional[list[str]]) -> None:
    if fieldnames is None:
        raise ImportError_("CSV file is empty.")

    normalized = {name.strip() for name in fieldnames if name is not None}
    missing = sorted(_REQUIRED_COLUMNS - normalized)
    if missing:
        raise ImportError_(f"CSV file is missing required columns: {', '.join(missing)}")


def _expense_from_row(raw_row: Optional[Dict[str, Any]]) -> Expense:
    normalized_row = _normalize_row(raw_row)
    amount_value = normalized_row["amount"]
    category_value = normalized_row["category"]
    date_value = normalized_row["date"]
    note_value = normalized_row.get("note", "")

    parsed_date = datetime.fromisoformat(str(date_value).strip())
    return Expense(
        amount=float(amount_value),
        category=str(category_value).strip(),
        note="" if note_value is None else str(note_value),
        date=parsed_date,
    )


def _normalize_row(raw_row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if raw_row is None:
        raise ValueError("Row is empty.")

    normalized: Dict[str, Any] = {}
    for key, value in raw_row.items():
        normalized_key = key.strip() if isinstance(key, str) else key
        if normalized_key is not None:
            normalized[str(normalized_key)] = value
    return normalized


def _expense_key(expense: Expense) -> Tuple[float, str, str]:
    return (expense.amount, expense.category, expense.date.isoformat())
