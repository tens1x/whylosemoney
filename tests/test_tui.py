from __future__ import annotations

from datetime import datetime

from whylosemoney import tui
from whylosemoney.config import Settings
from whylosemoney.models import Expense


def test_add_expense_flow(monkeypatch, capsys) -> None:
    responses = iter(["12.5", "food", "coffee", "2026-03-12"])
    captured: dict[str, Expense] = {}

    monkeypatch.setattr(tui, "get_all_categories", lambda: ["food", "other"])
    monkeypatch.setattr(tui, "validate_category", lambda category: True)
    monkeypatch.setattr(tui.Prompt, "ask", lambda *args, **kwargs: next(responses))

    def fake_add_expense(expense: Expense) -> Expense:
        captured["expense"] = expense
        return expense

    monkeypatch.setattr(tui.storage, "add_expense", fake_add_expense)

    tui._add_expense()

    assert captured["expense"].amount == 12.5
    assert captured["expense"].category == "food"
    assert captured["expense"].note == "coffee"
    assert captured["expense"].date == datetime(2026, 3, 12)
    assert "已添加支出" in capsys.readouterr().out


def test_list_expenses_empty(monkeypatch, capsys) -> None:
    responses = iter(["", ""])

    monkeypatch.setattr(tui, "load_config", lambda: Settings())
    monkeypatch.setattr(tui.Prompt, "ask", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(tui.storage, "list_expenses", lambda date_from=None, date_to=None: [])

    tui._list_expenses()

    assert "未找到支出记录" in capsys.readouterr().out


def test_settings_menu(monkeypatch, capsys) -> None:
    responses = iter(["1", "USD", "0"])
    state = {"settings": Settings()}
    calls: list[dict[str, object]] = []

    monkeypatch.setattr(tui.Prompt, "ask", lambda *args, **kwargs: next(responses))
    monkeypatch.setattr(tui, "load_config", lambda: state["settings"])

    def fake_update_config(**kwargs: object) -> Settings:
        calls.append(kwargs)
        state["settings"] = state["settings"].model_copy(update=kwargs)
        return state["settings"]

    monkeypatch.setattr(tui, "update_config", fake_update_config)

    tui._settings_menu()

    assert calls == [{"currency": "USD"}]
    assert state["settings"].currency == "USD"
    assert "设置已更新" in capsys.readouterr().out
