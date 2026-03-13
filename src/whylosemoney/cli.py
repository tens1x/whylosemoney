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
_PERIOD_LABELS = {"daily": "每日", "weekly": "每周", "monthly": "月度"}


def _parse_datetime(value: str, *, end_of_day: bool = False) -> datetime:
    """Parse a date or datetime string into a naive ``datetime``."""
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise click.BadParameter(
            "请使用 ISO 格式，如 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS。"
        ) from exc

    if len(value) == 10:
        selected_time = time.max.replace(microsecond=0) if end_of_day else time.min
        return datetime.combine(parsed.date(), selected_time)
    return parsed


def _render_expenses(expenses: list[Expense]) -> None:
    """Render expenses as a rich table."""
    table = RichTable(title="支出记录")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("日期", style="cyan")
    table.add_column("分类", style="green")
    table.add_column("金额", style="yellow", justify="right")
    table.add_column("备注")
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
    table = RichTable(title=f"{_PERIOD_LABELS[period]}汇总")
    table.add_column("时段", style="cyan")
    table.add_column("合计", style="yellow", justify="right")
    for label, total in summary.items():
        table.add_row(label, f"{total:.2f}")
    return table


def _build_breakdown_table(expenses: list[Expense]) -> RichTable:
    """Build the category breakdown table for the provided expenses."""
    totals = total_by_category(expenses)
    breakdown = percentage_breakdown(expenses)
    table = RichTable(title="分类明细")
    table.add_column("分类", style="green")
    table.add_column("合计", style="yellow", justify="right")
    table.add_column("占比", style="cyan", justify="right")
    for category, total in totals.items():
        table.add_row(category, f"{total:.2f}", f"{breakdown[category]:.2f}%")
    return table


def _build_top_expenses_table(expenses: list[Expense]) -> RichTable:
    """Build the top-expenses table for analysis output."""
    table = RichTable(title="最大支出")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("日期", style="cyan")
    table.add_column("分类", style="green")
    table.add_column("金额", style="yellow", justify="right")
    table.add_column("备注")
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
    """追踪支出，分析消费模式。"""
    if ctx.invoked_subcommand is None:
        import sys

        if sys.stdout.isatty():
            from whylosemoney.tui import main_menu

            main_menu()
        else:
            click.echo(ctx.get_help())


@cli.command("add")
@click.option("--amount", required=True, type=float, help="支出金额。")
@click.option("--category", required=True, type=str, help="支出分类。")
@click.option("--note", default="", show_default=True, type=str, help="备注（可选）。")
@click.option("--date", "date_value", type=str, help="支出日期（ISO 格式）。")
def add_command(amount: float, category: str, note: str, date_value: str | None) -> None:
    """添加一笔新支出。"""
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
        _console.print("[green]已添加支出：[/green]")
        _render_expenses([saved_expense])
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("list")
@click.option("--from", "date_from", type=str, help="起始日期（ISO 格式）。")
@click.option("--to", "date_to", type=str, help="截止日期（ISO 格式）。")
def list_command(date_from: str | None, date_to: str | None) -> None:
    """列出支出记录，支持按日期范围筛选。"""
    try:
        from_value = _parse_datetime(date_from) if date_from else None
        to_value = _parse_datetime(date_to, end_of_day=True) if date_to else None
        expenses = list_expenses(from_value, to_value)
        if not expenses:
            _console.print("[yellow]未找到支出记录。[/yellow]")
            return
        _render_expenses(expenses)
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("analyze")
@click.option(
    "--period",
    required=True,
    type=click.Choice(["monthly", "weekly", "daily"], case_sensitive=False),
    help="汇总周期。",
)
def analyze_command(period: str) -> None:
    """按时间段分析支出情况。"""
    try:
        expenses = list_expenses()
        if not expenses:
            _console.print("[yellow]没有可分析的支出数据。[/yellow]")
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
@click.option("--file", "file_path", required=True, type=click.Path(exists=True), help="要导入的 CSV 文件。")
@click.option("--resume", is_flag=True, default=False, help="从上次断点继续。")
def import_command(file_path: str, resume: bool) -> None:
    """从 CSV 文件批量导入支出。"""
    try:
        from pathlib import Path

        from whylosemoney.importer import import_csv

        result = import_csv(Path(file_path), resume=resume)
        _console.print(f"[green]成功：{result.succeeded}[/green]")
        _console.print(f"[red]失败：{result.failed}[/red]")
        _console.print(f"[yellow]跳过：{result.skipped}[/yellow]")
        if result.errors:
            for row_num, msg in result.errors:
                _console.print(f"  第 {row_num} 行：{msg}")
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)


@cli.command("delete")
@click.option("--id", "expense_id", required=True, type=click.UUID, help="支出 ID。")
def delete_command(expense_id: UUID) -> None:
    """按 ID 删除一笔支出。"""
    try:
        expense_id_str = str(expense_id)
        if not delete_expense(expense_id_str):
            raise click.ClickException(f"未找到该支出：{expense_id_str}")
        _console.print(f"[green]已删除支出：{expense_id_str}[/green]")
    except WhyLoseMoneyError as exc:
        _raise_click_exception(exc)
