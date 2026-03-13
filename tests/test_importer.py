from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from whylosemoney import importer, storage
from whylosemoney.models import Expense


def _patch_storage_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr(storage, "LOCK_FILE", tmp_path / "data.json.lock")
    monkeypatch.setattr(storage, "HISTORY_FILE", tmp_path / "history.jsonl")


def _write_csv(file_path: Path, rows: list[dict[str, str]]) -> None:
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["amount", "category", "date", "note"])
        writer.writeheader()
        writer.writerows(rows)


def test_import_valid_csv(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    checkpoint_file = tmp_path / "import_checkpoint.json"
    monkeypatch.setattr(importer, "CHECKPOINT_FILE", checkpoint_file)
    csv_file = tmp_path / "expenses.csv"
    _write_csv(
        csv_file,
        [
            {"amount": "12.5", "category": "food", "date": "2026-03-01", "note": "breakfast"},
            {"amount": "8.0", "category": "transport", "date": "2026-03-02", "note": "taxi"},
            {"amount": "99.9", "category": "shopping", "date": "2026-03-03", "note": "keyboard"},
        ],
    )

    result = importer.import_csv(csv_file)

    assert result.succeeded == 3
    assert result.failed == 0
    assert result.skipped == 0
    assert len(storage.list_expenses()) == 3
    assert checkpoint_file.exists() is False


def test_import_with_bad_row(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(importer, "CHECKPOINT_FILE", tmp_path / "import_checkpoint.json")
    csv_file = tmp_path / "expenses.csv"
    _write_csv(
        csv_file,
        [
            {"amount": "12.5", "category": "food", "date": "2026-03-01", "note": "breakfast"},
            {"amount": "-5", "category": "food", "date": "2026-03-02", "note": "invalid"},
            {"amount": "20", "category": "transport", "date": "2026-03-03", "note": "metro"},
        ],
    )

    result = importer.import_csv(csv_file)

    assert result.succeeded == 2
    assert result.failed == 1
    assert result.errors[0][0] == 3
    assert "金额必须为正数" in result.errors[0][1]


def test_import_skips_duplicates(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(importer, "CHECKPOINT_FILE", tmp_path / "import_checkpoint.json")
    existing = Expense(
        amount=12.5,
        category="food",
        note="breakfast",
        date=datetime(2026, 3, 1),
    )
    storage.add_expense(existing)

    csv_file = tmp_path / "expenses.csv"
    _write_csv(
        csv_file,
        [
            {"amount": "12.5", "category": "food", "date": "2026-03-01T00:00:00", "note": "again"},
        ],
    )

    result = importer.import_csv(csv_file)

    assert result.succeeded == 0
    assert result.failed == 0
    assert result.skipped == 1
    assert len(storage.list_expenses()) == 1


def test_import_resume(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    checkpoint_file = tmp_path / "import_checkpoint.json"
    monkeypatch.setattr(importer, "CHECKPOINT_FILE", checkpoint_file)
    csv_file = tmp_path / "expenses.csv"
    _write_csv(
        csv_file,
        [
            {"amount": "10", "category": "food", "date": "2026-03-01", "note": "first"},
            {"amount": "20", "category": "transport", "date": "2026-03-02", "note": "second"},
            {"amount": "30", "category": "shopping", "date": "2026-03-03", "note": "third"},
        ],
    )
    importer._save_checkpoint(csv_file, 3)

    result = importer.import_csv(csv_file, resume=True)

    items = storage.list_expenses()
    assert result.succeeded == 1
    assert result.failed == 0
    assert result.skipped == 0
    assert len(items) == 1
    assert items[0].note == "third"
    assert checkpoint_file.exists() is False
