"""CLI entry point for WhyLoseMoney."""

from __future__ import annotations

from datetime import datetime, time
from uuid import UUID

import click
from tabulate import tabulate

from whylosemoney.analyzer import (
    daily_summary,
    monthly_summary,
    percentage_breakdown,
    top_expenses,
    total_by_category,
    weekly_summary,
)
from whylosemoney.categories import add_custom_category, validate_category
from whylosemoney.models import Expense
from whylosemoney.storage import add_expense, delete_expense, list_expenses


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


def _render_expenses(expenses: list[Expense]) -> str:
    """Build a table for expense output."""
    rows = [
        [
            expense.id,
            expense.date.strftime("%Y-%m-%d %H:%M:%S"),
            expense.category,
            f"{expense.amount:.2f}",
            expense.note,
        ]
        for expense in expenses
    ]
    return tabulate(rows, headers=["ID", "Date", "Category", "Amount", "Note"], tablefmt="github")


@click.group()
def cli() -> None:
    """Track expenses and analyze spending patterns."""


@cli.command("add")
@click.option("--amount", required=True, type=float, help="Expense amount.")
@click.option("--category", required=True, type=str, help="Expense category.")
@click.option("--note", default="", show_default=True, type=str, help="Optional note.")
@click.option("--date", "date_value", type=str, help="Expense date in ISO format.")
def add_command(amount: float, category: str, note: str, date_value: str | None) -> None:
    """Add a new expense."""
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
    click.echo("Expense added:")
    click.echo(_render_expenses([saved_expense]))


@cli.command("list")
@click.option("--from", "date_from", type=str, help="Start date in YYYY-MM-DD or ISO format.")
@click.option("--to", "date_to", type=str, help="End date in YYYY-MM-DD or ISO format.")
def list_command(date_from: str | None, date_to: str | None) -> None:
    """List expenses with optional date range filtering."""
    from_value = _parse_datetime(date_from) if date_from else None
    to_value = _parse_datetime(date_to, end_of_day=True) if date_to else None
    expenses = list_expenses(from_value, to_value)
    if not expenses:
        click.echo("No expenses found.")
        return
    click.echo(_render_expenses(expenses))


@cli.command("analyze")
@click.option(
    "--period",
    required=True,
    type=click.Choice(["monthly", "weekly", "daily"], case_sensitive=False),
    help="Summary period.",
)
def analyze_command(period: str) -> None:
    """Analyze expenses for a selected period."""
    expenses = list_expenses()
    if not expenses:
        click.echo("No expenses available for analysis.")
        return

    summary_map = {
        "daily": daily_summary,
        "weekly": weekly_summary,
        "monthly": monthly_summary,
    }
    summary = summary_map[period](expenses)
    breakdown = percentage_breakdown(expenses)
    summary_rows = [[label, f"{total:.2f}"] for label, total in summary.items()]
    category_rows = [
        [category, f"{total:.2f}", f"{breakdown[category]:.2f}%"]
        for category, total in total_by_category(expenses).items()
    ]
    top_rows = [
        [
            expense.id,
            expense.date.strftime("%Y-%m-%d %H:%M:%S"),
            expense.category,
            f"{expense.amount:.2f}",
            expense.note,
        ]
        for expense in top_expenses(expenses)
    ]

    click.echo(f"{period.capitalize()} summary:")
    click.echo(tabulate(summary_rows, headers=["Period", "Total"], tablefmt="github"))
    click.echo("")
    click.echo("Category breakdown:")
    click.echo(
        tabulate(
            category_rows,
            headers=["Category", "Total", "Percentage"],
            tablefmt="github",
        )
    )
    click.echo("")
    click.echo("Top expenses:")
    click.echo(
        tabulate(
            top_rows,
            headers=["ID", "Date", "Category", "Amount", "Note"],
            tablefmt="github",
        )
    )


@cli.command("delete")
@click.option("--id", "expense_id", required=True, type=click.UUID, help="Expense ID.")
def delete_command(expense_id: UUID) -> None:
    """Delete an expense by ID."""
    expense_id_str = str(expense_id)
    if not delete_expense(expense_id_str):
        raise click.ClickException(f"Expense not found: {expense_id_str}")
    click.echo(f"Deleted expense: {expense_id_str}")
