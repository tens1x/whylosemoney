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
_PERIOD_LABELS = {"daily": "每日", "weekly": "每周", "monthly": "月度"}


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
        console.print("1. 添加支出")
        console.print("2. 查看支出")
        console.print("3. 分析消费")
        console.print("4. 删除支出")
        console.print("5. 导入 CSV")
        console.print("6. 操作历史")
        console.print("7. 设置")
        console.print("0. 退出")

        try:
            choice = Prompt.ask("请选择", choices=["0", "1", "2", "3", "4", "5", "6", "7"])
        except KeyboardInterrupt:
            console.print("[yellow]再见！[/yellow]")
            break

        if choice == "0":
            break
        actions[choice]()
        console.print()


def _add_expense() -> None:
    """Prompt the user for expense fields and save the result."""
    try:
        categories = ", ".join(get_all_categories())
        amount = float(Prompt.ask("金额"))
        category = Prompt.ask(f"分类（{categories}）").strip().lower()
        note = Prompt.ask("备注", default="")
        date_input = Prompt.ask(
            "日期（YYYY-MM-DD 或 ISO 格式）",
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
        console.print(f"[green]已添加支出 {saved_expense.id}。[/green]")
    except KeyboardInterrupt:
        console.print("[yellow]已取消。[/yellow]")
    except (ValidationError, ValueError, WhyLoseMoneyError) as exc:
        console.print(f"[red]错误：{exc}[/red]")


def _list_expenses() -> None:
    """Show expenses in a paginated rich table."""
    try:
        settings = load_config()
        date_from_input = Prompt.ask("起始日期（可选）", default="").strip()
        date_to_input = Prompt.ask("截止日期（可选）", default="").strip()
        date_from = _parse_datetime(date_from_input) if date_from_input else None
        date_to = _parse_datetime(date_to_input, end_of_day=True) if date_to_input else None

        expenses = storage.list_expenses(date_from=date_from, date_to=date_to)
        if not expenses:
            console.print("[yellow]未找到支出记录。[/yellow]")
            return

        page_size = max(settings.page_size, 1)
        total_pages = (len(expenses) + page_size - 1) // page_size
        current_page = 0

        while True:
            start_index = current_page * page_size
            end_index = start_index + page_size
            page_items = expenses[start_index:end_index]

            table = Table(title="支出记录")
            table.add_column("ID", style="dim", no_wrap=True)
            table.add_column("日期", style="cyan")
            table.add_column("分类", style="green")
            table.add_column("金额", style="yellow", justify="right")
            table.add_column("备注", style="white")

            for expense in page_items:
                table.add_row(
                    expense.id,
                    _format_expense_date(expense.date, settings),
                    expense.category,
                    f"{expense.amount:.2f}",
                    expense.note,
                )

            console.print(table)
            console.print(f"第 {current_page + 1} 页 / 共 {total_pages} 页")
            action = Prompt.ask(
                "[n] 下一页 / [p] 上一页 / [q] 返回",
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
        console.print(f"[red]错误：{exc}[/red]")


def _analyze() -> None:
    """Render spending summaries, category breakdown, and top expenses."""
    try:
        settings = load_config()
        period = Prompt.ask(
            "汇总周期",
            choices=["daily", "weekly", "monthly"],
            default="monthly",
        )
        expenses = storage.list_expenses()
        if not expenses:
            console.print("[yellow]没有可分析的支出数据。[/yellow]")
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

        summary_table = Table(title=f"{_PERIOD_LABELS[period]}汇总")
        summary_table.add_column("时段", style="cyan")
        summary_table.add_column("合计", style="yellow", justify="right")
        for label, total in summary.items():
            summary_table.add_row(label, f"{total:.2f}")

        breakdown_table = Table(title="分类明细")
        breakdown_table.add_column("分类", style="green")
        breakdown_table.add_column("合计", style="yellow", justify="right")
        breakdown_table.add_column("占比", style="cyan", justify="right")
        for category, total in totals.items():
            breakdown_table.add_row(category, f"{total:.2f}", f"{breakdown.get(category, 0):.2f}%")

        top_table = Table(title="最大支出")
        top_table.add_column("ID", style="dim", no_wrap=True)
        top_table.add_column("日期", style="cyan")
        top_table.add_column("分类", style="green")
        top_table.add_column("金额", style="yellow", justify="right")
        top_table.add_column("备注", style="white")
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
        console.print("[yellow]已取消。[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]错误：{exc}[/red]")


def _delete_expense() -> None:
    """Prompt for an expense ID and delete it after confirmation."""
    try:
        expense_id = Prompt.ask("支出 ID").strip()
        if not Confirm.ask("确定删除？", default=False):
            console.print("[yellow]已取消。[/yellow]")
            return

        if storage.delete_expense(expense_id):
            console.print(f"[green]已删除支出 {expense_id}。[/green]")
        else:
            console.print(f"[yellow]未找到该支出：{expense_id}[/yellow]")
    except KeyboardInterrupt:
        console.print("[yellow]已取消。[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]错误：{exc}[/red]")


def _import_csv_menu() -> None:
    """Prompt for a CSV path and display the import summary."""
    try:
        file_path_value = Prompt.ask("CSV 文件路径").strip()
        resume = Confirm.ask("从断点继续？", default=False)
        result = import_csv(Path(file_path_value), resume=resume)
        _render_import_result(result)
    except KeyboardInterrupt:
        console.print("[yellow]已取消。[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]错误：{exc}[/red]")


def _view_history() -> None:
    """Show recent audit log entries."""
    try:
        history = storage.get_history()
        if not history:
            console.print("[yellow]暂无操作历史。[/yellow]")
            return

        table = Table(title="操作历史")
        table.add_column("时间", style="cyan")
        table.add_column("操作", style="green")
        table.add_column("详情", style="white")

        for entry in history:
            table.add_row(
                str(entry.get("timestamp", "")),
                str(entry.get("operation", "")),
                json.dumps(entry.get("detail", {}), ensure_ascii=False, sort_keys=True),
            )
        console.print(table)
    except KeyboardInterrupt:
        console.print("[yellow]已取消。[/yellow]")
    except WhyLoseMoneyError as exc:
        console.print(f"[red]错误：{exc}[/red]")


def _settings_menu() -> None:
    """Inspect and update persistent application settings."""
    try:
        while True:
            settings = load_config()
            console.print(Panel(_format_settings(settings), title="当前设置"))
            console.print("1. 货币")
            console.print("2. 日期格式")
            console.print("3. 每页条数")
            console.print("4. 默认分类")
            console.print("5. 自定义分类")
            console.print("0. 返回")

            choice = Prompt.ask(
                "选择要编辑的设置",
                choices=["0", "1", "2", "3", "4", "5"],
            )
            if choice == "0":
                return

            updated_settings = settings
            if choice == "1":
                currency = Prompt.ask("货币", default=settings.currency).strip()
                updated_settings = update_config(currency=currency)
            elif choice == "2":
                date_format = Prompt.ask("日期格式", default=settings.date_format).strip()
                updated_settings = update_config(date_format=date_format)
            elif choice == "3":
                page_size = IntPrompt.ask("每页条数", default=settings.page_size)
                updated_settings = update_config(page_size=page_size)
            elif choice == "4":
                default_category = Prompt.ask(
                    "默认分类",
                    default=settings.default_category,
                ).strip().lower()
                if not validate_category(default_category):
                    default_category = add_custom_category(default_category)
                updated_settings = update_config(default_category=default_category)
            elif choice == "5":
                raw_categories = Prompt.ask(
                    "自定义分类（逗号分隔）",
                    default=", ".join(settings.custom_categories),
                )
                categories = _parse_custom_categories(raw_categories)
                for category in categories:
                    if not validate_category(category):
                        add_custom_category(category)
                updated_settings = update_config(custom_categories=categories)

            console.print("[green]设置已更新。[/green]")
            console.print(Panel(_format_settings(updated_settings), title="更新后的设置"))
    except KeyboardInterrupt:
        console.print("[yellow]已取消。[/yellow]")
    except (ValidationError, ValueError, WhyLoseMoneyError) as exc:
        console.print(f"[red]错误：{exc}[/red]")


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
    summary = Table(title="导入汇总")
    summary.add_column("成功", style="green", justify="right")
    summary.add_column("失败", style="red", justify="right")
    summary.add_column("跳过", style="yellow", justify="right")
    summary.add_row(str(result.succeeded), str(result.failed), str(result.skipped))
    console.print(summary)

    if result.errors:
        error_table = Table(title="导入错误")
        error_table.add_column("行", style="cyan", justify="right")
        error_table.add_column("错误", style="red")
        for row_number, message in result.errors:
            error_table.add_row(str(row_number), message)
        console.print(error_table)


def _format_settings(settings: Settings) -> str:
    custom_categories = ", ".join(settings.custom_categories) or "（无）"
    return (
        f"货币：{settings.currency}\n"
        f"日期格式：{settings.date_format}\n"
        f"每页条数：{settings.page_size}\n"
        f"默认分类：{settings.default_category}\n"
        f"自定义分类：{custom_categories}"
    )


def _parse_custom_categories(raw_categories: str) -> list[str]:
    parsed = [item.strip().lower() for item in raw_categories.split(",") if item.strip()]
    return sorted(set(parsed))


if __name__ == "__main__":
    try:
        main_menu()
    except KeyboardInterrupt:
        console.print("[yellow]再见！[/yellow]")
        sys.exit(0)
