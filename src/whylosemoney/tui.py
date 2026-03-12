"""Interactive terminal user interface for WhyLoseMoney."""

from __future__ import annotations

import json
import sys
from datetime import datetime, time
from pathlib import Path
from typing import Callable

from pydantic import ValidationError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from whylosemoney import __version__, analyzer, storage
from whylosemoney.categories import add_custom_category, get_all_categories, validate_category
from whylosemoney.config import Settings, load_config, update_config
from whylosemoney.exceptions import WhyLoseMoneyError
from whylosemoney.importer import ImportResult, import_csv
from whylosemoney.models import Expense

console = Console()


def main_menu() -> None:
    """Run the main interactive menu loop."""
    actions: dict[str, Callable[[], None]] = {
        "1": _add_expense,
        "2": _list_expenses,
        "3": _analyze,
        "4": _delete_expense,
        "5": _import_csv_menu,
        "6": _view_history,
        "7": _settings_menu,
    }

    while True:
        console.print(Panel.fit(f"WhyLoseMoney v{__version__}"))
        console.print("1. Add expense")
        console.print("2. List expenses")
        console.print("3. Analyze spending")
        console.print("4. Delete expense")
        console.print("5. Import from CSV")
        console.print("6. View history")
        console.print("7. Settings")
        console.print("0. Exit")

        try:
            choice = Prompt.ask("Select an option", choices=["0", "1", "2", "3", "4", "5", "6", "7"])
        except KeyboardInterrupt:
            console.print("[yellow]Goodbye![/yellow]")
            break

        if choice == "0":
            break
        actions[choice]()
        console.print()


def _add_expense() -> None:
    """Prompt the user for expense fields and save the result."""
    try:
        categories = ", ".join(get_all_categories())
        amount = float(Prompt.ask("Amount"))
        category = Prompt.ask(f"Category ({categories})").strip().lower()
        note = Prompt.ask("Note", default="")
        date_input = Prompt.ask(
            "Date (YYYY-MM-DD or ISO datetime)",
            default=datetime.now().date().isoformat(),
        ).strip()
        expense_date = datetime.fromisoformat(date_input)

        if not validate_category(category):
            category = add_custom_category(category)

        expense = Expense(
            amount=amount,
            category=category,
            note=note,
            date=expense_date,
        )
        saved_expense = storage.add_expense(expense)
        console.print(f"[green]Added expense {saved_expense.id}.[/green]")
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
    except (ValidationError, ValueError, WhyLoseMoneyError) as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _list_expenses() -> None:
    """Show expenses in a paginated rich table."""
    try:
        settings = load_config()
        date_from_input = Prompt.ask("From date (optional)", default="").strip()
        date_to_input = Prompt.ask("To date (optional)", default="").strip()
        date_from = _parse_datetime(date_from_input) if date_from_input else None
        date_to = _parse_datetime(date_to_input, end_of_day=True) if date_to_input else None

        expenses = storage.list_expenses(date_from=date_from, date_to=date_to)
        if not expenses:
            console.print("[yellow]No expenses found.[/yellow]")
            return

        page_size = max(settings.page_size, 1)
        total_pages = (len(expenses) + page_size - 1) // page_size
        current_page = 0

        while True:
            start_index = current_page * page_size
            end_index = start_index + page_size
            page_items = expenses[start_index:end_index]

            table = Table(title="Expenses")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("Date", style="cyan")
            table.add_column("Category", style="green")
            table.add_column("Amount", style="yellow", justify="right")
            table.add_column("Note", style="white")

            for expense in page_items:
                table.add_row(
                    expense.id,
                    _format_expense_date(expense.date, settings),
                    expense.category,
                    f"{expense.amount:.2f}",
                    expense.note,
                )

            console.print(table)
            console.print(f"Page {current_page + 1} of {total_pages}")
            action = Prompt.ask(
                "[n]ext / [p]revious / [q]uit",
                choices=["n", "p", "q"],
                default="q",
            )
            if action == "q":
                return
            if action == "n" and current_page < total_pages - 1:
                current_page += 1
            if action == "p" and current_page > 0:
                current_page -= 1
    except KeyboardInterrupt:
        return
    except (ValidationError, ValueError, WhyLoseMoneyError) as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _analyze() -> None:
    """Render spending summaries, category breakdown, and top expenses."""
    try:
        settings = load_config()
        period = Prompt.ask(
            "Summary period",
            choices=["daily", "weekly", "monthly"],
            default="monthly",
        )
        expenses = storage.list_expenses()
        if not expenses:
            console.print("[yellow]No expenses available for analysis.[/yellow]")
            return

        summary_map = {
            "daily": analyzer.daily_summary,
            "weekly": analyzer.weekly_summary,
            "monthly": analyzer.monthly_summary,
        }
        summary = summary_map[period](expenses)
        totals = analyzer.total_by_category(expenses)
        breakdown = analyzer.percentage_breakdown(expenses)
        top_items = analyzer.top_expenses(expenses, n=5)

        summary_table = Table(title=f"{period.capitalize()} Summary")
        summary_table.add_column("Period", style="cyan")
        summary_table.add_column("Total", style="yellow", justify="right")
        for label, total in summary.items():
            summary_table.add_row(label, f"{total:.2f}")

        breakdown_table = Table(title="Category Breakdown")
        breakdown_table.add_column("Category", style="green")
        breakdown_table.add_column("Total", style="yellow", justify="right")
        breakdown_table.add_column("Percentage", style="cyan", justify="right")
        for category, total in totals.items():
            breakdown_table.add_row(category, f"{total:.2f}", f"{breakdown.get(category, 0):.2f}%")

        top_table = Table(title="Top 5 Expenses")
        top_table.add_column("ID", style="dim", no_wrap=True)
        top_table.add_column("Date", style="cyan")
        top_table.add_column("Category", style="green")
        top_table.add_column("Amount", style="yellow", justify="right")
        top_table.add_column("Note", style="white")
        for expense in top_items:
            top_table.add_row(
                expense.id,
                _format_expense_date(expense.date, settings),
                expense.category,
                f"{expense.amount:.2f}",
                expense.note,
            )

        console.print(summary_table)
        console.print(breakdown_table)
        console.print(top_table)
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _delete_expense() -> None:
    """Prompt for an expense ID and delete it after confirmation."""
    try:
        expense_id = Prompt.ask("Expense ID").strip()
        if not Confirm.ask("Are you sure?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            return

        if storage.delete_expense(expense_id):
            console.print(f"[green]Deleted expense {expense_id}.[/green]")
        else:
            console.print(f"[yellow]Expense not found: {expense_id}[/yellow]")
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _import_csv_menu() -> None:
    """Prompt for a CSV path and display the import summary."""
    try:
        file_path_value = Prompt.ask("CSV file path").strip()
        resume = Confirm.ask("Resume from checkpoint?", default=False)
        result = import_csv(Path(file_path_value), resume=resume)
        _render_import_result(result)
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _view_history() -> None:
    """Show recent audit log entries."""
    try:
        history = storage.get_history()
        if not history:
            console.print("[yellow]No history available.[/yellow]")
            return

        table = Table(title="History")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Operation", style="green")
        table.add_column("Detail", style="white")

        for entry in history:
            table.add_row(
                str(entry.get("timestamp", "")),
                str(entry.get("operation", "")),
                json.dumps(entry.get("detail", {}), ensure_ascii=False, sort_keys=True),
            )
        console.print(table)
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _settings_menu() -> None:
    """Inspect and update persistent application settings."""
    try:
        while True:
            settings = load_config()
            console.print(Panel(_format_settings(settings), title="Current Settings"))
            console.print("1. Currency")
            console.print("2. Date format")
            console.print("3. Page size")
            console.print("4. Default category")
            console.print("5. Custom categories")
            console.print("0. Back")

            choice = Prompt.ask(
                "Select setting to edit",
                choices=["0", "1", "2", "3", "4", "5"],
            )
            if choice == "0":
                return

            updated_settings = settings
            if choice == "1":
                currency = Prompt.ask("Currency", default=settings.currency).strip()
                updated_settings = update_config(currency=currency)
            elif choice == "2":
                date_format = Prompt.ask("Date format", default=settings.date_format).strip()
                updated_settings = update_config(date_format=date_format)
            elif choice == "3":
                page_size = IntPrompt.ask("Page size", default=settings.page_size)
                updated_settings = update_config(page_size=page_size)
            elif choice == "4":
                default_category = Prompt.ask(
                    "Default category",
                    default=settings.default_category,
                ).strip().lower()
                if not validate_category(default_category):
                    default_category = add_custom_category(default_category)
                updated_settings = update_config(default_category=default_category)
            elif choice == "5":
                raw_categories = Prompt.ask(
                    "Custom categories (comma separated)",
                    default=", ".join(settings.custom_categories),
                )
                categories = _parse_custom_categories(raw_categories)
                for category in categories:
                    if not validate_category(category):
                        add_custom_category(category)
                updated_settings = update_config(custom_categories=categories)

            console.print("[green]Settings updated.[/green]")
            console.print(Panel(_format_settings(updated_settings), title="Updated Settings"))
    except KeyboardInterrupt:
        console.print("[yellow]Cancelled.[/yellow]")
    except (ValidationError, ValueError, WhyLoseMoneyError) as exc:
        console.print(f"[red]Error: {exc}[/red]")


def _parse_datetime(value: str, *, end_of_day: bool = False) -> datetime:
    parsed = datetime.fromisoformat(value)
    if len(value) == 10:
        selected_time = time.max.replace(microsecond=0) if end_of_day else time.min
        return datetime.combine(parsed.date(), selected_time)
    return parsed


def _format_expense_date(value: datetime, settings: Settings) -> str:
    base = value.strftime(settings.date_format)
    if value.time() == time.min:
        return base
    return f"{base} {value.strftime('%H:%M:%S')}"


def _render_import_result(result: ImportResult) -> None:
    summary = Table(title="Import Summary")
    summary.add_column("Succeeded", style="green", justify="right")
    summary.add_column("Failed", style="red", justify="right")
    summary.add_column("Skipped", style="yellow", justify="right")
    summary.add_row(str(result.succeeded), str(result.failed), str(result.skipped))
    console.print(summary)

    if result.errors:
        error_table = Table(title="Import Errors")
        error_table.add_column("Row", style="cyan", justify="right")
        error_table.add_column("Error", style="red")
        for row_number, message in result.errors:
            error_table.add_row(str(row_number), message)
        console.print(error_table)


def _format_settings(settings: Settings) -> str:
    custom_categories = ", ".join(settings.custom_categories) or "(none)"
    return (
        f"Currency: {settings.currency}\n"
        f"Date format: {settings.date_format}\n"
        f"Page size: {settings.page_size}\n"
        f"Default category: {settings.default_category}\n"
        f"Custom categories: {custom_categories}"
    )


def _parse_custom_categories(raw_categories: str) -> list[str]:
    parsed = [item.strip().lower() for item in raw_categories.split(",") if item.strip()]
    return sorted(set(parsed))


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("[yellow]Goodbye![/yellow]")
        sys.exit(0)
