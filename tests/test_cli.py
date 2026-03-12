from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

import click
from click.testing import CliRunner

import whylosemoney.cli as cli_module
from whylosemoney import importer, storage
from whylosemoney.exceptions import StorageError
from whylosemoney.models import Expense


def _patch_storage_paths(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "DATA_FILE", tmp_path / "data.json")
    monkeypatch.setattr(storage, "LOCK_FILE", tmp_path / "data.json.lock")
    monkeypatch.setattr(storage, "HISTORY_FILE", tmp_path / "history.jsonl")
    monkeypatch.setattr(cli_module, "add_expense", storage.add_expense)
    monkeypatch.setattr(cli_module, "delete_expense", storage.delete_expense)
    monkeypatch.setattr(cli_module, "list_expenses", storage.list_expenses)


def _write_csv(file_path: Path, rows: list[dict[str, str]]) -> None:
    with file_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["amount", "category", "date", "note"])
        writer.writeheader()
        writer.writerows(rows)


def test_cli_without_subcommand_shows_help_when_not_tty() -> None:
    runner = CliRunner()

    result = runner.invoke(cli_module.cli, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "add" in result.output
    assert "import" in result.output


def test_cli_without_subcommand_launches_tui_when_tty(monkeypatch) -> None:
    called = {"value": False}

    def fake_main_menu() -> None:
        called["value"] = True

    class _TTYStdout:
        def isatty(self) -> bool:
            return True

    import whylosemoney.tui as tui_module

    monkeypatch.setattr(tui_module, "main_menu", fake_main_menu)
    monkeypatch.setattr(sys, "stdout", _TTYStdout())

    ctx = click.Context(cli_module.cli)
    with ctx:
        cli_module.cli.callback()

    assert called["value"] is True


def test_add_command_renders_expense_table(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        cli_module.cli,
        [
            "add",
            "--amount",
            "35.6",
            "--category",
            "food",
            "--note",
            "lunch",
            "--date",
            "2026-03-11",
        ],
    )

    assert result.exit_code == 0
    assert "Expense added:" in result.output
    assert "Expenses" in result.output
    assert "food" in result.output
    assert "35.60" in result.output


def test_analyze_command_renders_rich_sections(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    runner = CliRunner()
    storage.add_expense(Expense(amount=20, category="food", note="lunch", date=datetime(2026, 3, 1, 12, 0)))
    storage.add_expense(Expense(amount=80, category="shopping", note="mouse", date=datetime(2026, 3, 3, 20, 0)))

    result = runner.invoke(cli_module.cli, ["analyze", "--period", "monthly"])

    assert result.exit_code == 0
    assert "Monthly Summary" in result.output
    assert "Category Breakdown" in result.output
    assert "Top Expenses" in result.output
    assert "shopping" in result.output
    assert "80.00" in result.output


def test_import_command_reports_summary(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    monkeypatch.setattr(importer, "CHECKPOINT_FILE", tmp_path / "import_checkpoint.json")
    runner = CliRunner()
    csv_file = tmp_path / "expenses.csv"
    _write_csv(
        csv_file,
        [
            {"amount": "12.5", "category": "food", "date": "2026-03-01", "note": "breakfast"},
            {"amount": "8.0", "category": "transport", "date": "2026-03-02", "note": "taxi"},
        ],
    )

    result = runner.invoke(cli_module.cli, ["import", "--file", str(csv_file)])

    assert result.exit_code == 0
    assert "Succeeded: 2" in result.output
    assert "Failed: 0" in result.output
    assert "Skipped: 0" in result.output


def test_list_command_wraps_storage_errors(tmp_path: Path, monkeypatch) -> None:
    _patch_storage_paths(tmp_path, monkeypatch)
    runner = CliRunner()

    def raise_storage_error(*args, **kwargs) -> list[Expense]:
        raise StorageError("storage is broken")

    monkeypatch.setattr(cli_module, "list_expenses", raise_storage_error)

    result = runner.invoke(cli_module.cli, ["list"])

    assert result.exit_code != 0
    assert "Error: storage is broken" in result.output
