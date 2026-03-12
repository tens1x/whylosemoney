"""CLI entry point for WhyLoseMoney."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

import click
from rich.console import Console
from rich.table import Table as RichTable

from whylosemoney.analyzer import (
    daily_summary,
    monthly_summary,
    percentage_breakdown,
    top_expenses,
    total_by_category,
    weekly_summary,
)
from whylosemoney.categories import add_custom_category, validate_category
from whylosemoney.exceptions import WhyLoseMoneyError
from whylosemoney.models import Expense
from whylosemoney.storage import add_expense, delete_expense, list_expenses

_console = Console()


def _parse_datetime(value: str, *, end_of_day: bool = False) -> datetime:
    """Parse a date or datetime string into a naive ``datetime``."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise click.BadParameter(
            "Use ISO format such as YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS."
        ) from exc

    if len(value) == 10:
        selected_time = time.max.replace(microsecond=0) if end_of_day else time.min
        return datetime.combine(parsed.date(), selected_time)
    return parsed


def _render_expenses(expenses: list[Expense]) -> None:
    """Render expenses as a rich table."""
    table = RichTable(title="Expenses")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Date", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Note")
    for expense in expenses:
        table.add_row(
            expense.id,
            expense.date.strftime("%Y-%m-%d %H:%M:%S"),
            expense.category,
            f"{expense.amount:.2f}",
            expense.note,
        )
    _console.print(table)


def _raise_click_exception(exc: WhyLoseMoneyError) -> None:
    """Re-raise a domain exception as a Click-friendly error."""
    raise click.ClickException(str(exc)) from exc


def _build_summary_table(period: str, summary: dict[str, float]) -> RichTable:
    """Build the summary table for the selected period."""
    table = RichTable(title=f"{period.capitalize()} Summary")
    table.add_column("Period", style="cyan")
    table.add_column("Total", style="yellow", justify="right")
    for label, total in summary.items():
        table.add_row(label, f"{total:.2f}")
    return table


def _build_breakdown_table(expenses: list[Expense]) -> RichTable:
    """Build the category breakdown table for the provided expenses."""
    totals = total_by_category(expenses)
    breakdown = percentage_breakdown(expenses)
    table = RichTable(title="Category Breakdown")
    table.add_column("Category", style="green")
    table.add_column("Total", style="yellow", justify="right")
    table.add_column("Percentage", style="cyan", justify="right")
    for category, total in totals.items():
        table.add_row(category, f"{total:.2f}", f"{breakdown[category]:.2f}%")
    return table


def _build_top_expenses_table(expenses: list[Expense]) -> RichTable:
    """Build the top-expenses table for analysis output."""
    table = RichTable(title="Top Expenses")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Date", style="cyan")
    table.add_column("Category", style="green")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Note")
    for expense in top_expenses(expenses):
        table.add_row(
            expense.id,
            expense.date.strftime("%Y-%m-%d %H:%M:%S"),
            expense.category,
            f"{expense.amount:.2f}",
            expense.note,
        )
    return table


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Track expenses and analyze spending patterns."""
    if ctx.invoked_subcommand is None:
        import sys

        if sys.stdout.isatty():
            from whylosemoney.tui import main_menu

            main_menu()
        else:
            click.echo(ctx.get_help())


@cli.command("add")
@click.option("--amount", required=True, type=float, help="Expense amount.")
@click.option("--category", required=True, type=str, help="Expense category.")
@click.option("--note", default="", show_default=True, type=str, help="Optional note.")
@click.option("--date", "date_value", type=str, help="Expense date in ISO format.")
def add_command(amount: float, category: str, note: str, date_value: str | None) -> None:
    """Add a new expense."""
    try:
        normalized_category = category.strip().lower()
        if not validate_category(normalized_category):
            normalized_category = add_custom_category(normalized_category)

        expense_date = _parse_datetime(date_value) if date_value else datetime.now()
        expense = Expense(
            amount=amount,
            category=normalized_category,
            note=note,
            date=expense_date,
        )
        saved_expense = add_expense(expense)
        _console.print("[green]Expense added:[/green]")
        _render_expenses([saved_expense])
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("list")
@click.option("--from", "date_from", type=str, help="Start date in YYYY-MM-DD or ISO format.")
@click.option("--to", "date_to", type=str, help="End date in YYYY-MM-DD or ISO format.")
def list_command(date_from: str | None, date_to: str | None) -> None:
    """List expenses with optional date range filtering."""
    try:
        from_value = _parse_datetime(date_from) if date_from else None
        to_value = _parse_datetime(date_to, end_of_day=True) if date_to else None
        expenses = list_expenses(from_value, to_value)
        if not expenses:
            _console.print("[yellow]No expenses found.[/yellow]")
            return
        _render_expenses(expenses)
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("analyze")
@click.option(
    "--period",
    required=True,
    type=click.Choice(["monthly", "weekly", "daily"], case_sensitive=False),
    help="Summary period.",
)
def analyze_command(period: str) -> None:
    """Analyze expenses for a selected period."""
    try:
        expenses = list_expenses()
        if not expenses:
            _console.print("[yellow]No expenses available for analysis.[/yellow]")
            return

        summary_map = {
            "daily": daily_summary,
            "weekly": weekly_summary,
            "monthly": monthly_summary,
        }
        summary = summary_map[period](expenses)

        _console.print(_build_summary_table(period, summary))
        _console.print(_build_breakdown_table(expenses))
        _console.print(_build_top_expenses_table(expenses))
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("import")
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="CSV file to import.")
@click.option("--resume", is_flag=True, default=False, help="Resume from last checkpoint.")
def import_command(file_path: str, resume: bool) -> None:
    """Import expenses from a CSV file."""
    try:
        from pathlib import Path

        from whylosemoney.importer import import_csv

        result = import_csv(Path(file_path), resume=resume)
        _console.print(f"[green]Succeeded: {result.succeeded}[/green]")
        _console.print(f"[red]Failed: {result.failed}[/red]")
        _console.print(f"[yellow]Skipped: {result.skipped}[/yellow]")
        if result.errors:
            for row_num, msg in result.errors:
                _console.print(f"  Row {row_num}: {msg}")
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("delete")
@click.option("--id", "expense_id", required=True, type=click.UUID, help="Expense ID.")
def delete_command(expense_id: UUID) -> None:
    """Delete an expense by ID."""
    try:
        expense_id_str = str(expense_id)
        if not delete_expense(expense_id_str):
            raise click.ClickException(f"Expense not found: {expense_id_str}")
        _console.print(f"[green]Deleted expense: {expense_id_str}[/green]")
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)
