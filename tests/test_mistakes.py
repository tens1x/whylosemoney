from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from whylosemoney.analysis.mistakes import (
    detect_concentration,
    detect_overtrading,
)
from whylosemoney.models import Position, Trade


def _make_trade(symbol: str, qty: float, price: float, dt: str) -> Trade:
    return Trade(
        symbol=symbol,
        datetime=datetime.fromisoformat(dt),
        quantity=qty,
        price=price,
        proceeds=qty * price,
        commission=-1.0,
        realized_pnl=0.0,
    )


def test_detect_overtrading_weekly():
    trades = [
        _make_trade("AAPL", 10, 150, f"2024-01-{15 + i} 10:00")
        for i in range(6)
    ]
    mistakes = detect_overtrading(trades)
    weekly_mistakes = [m for m in mistakes if "周" in m.description]
    assert len(weekly_mistakes) >= 1


def test_detect_overtrading_no_issue():
    trades = [
        _make_trade("AAPL", 10, 150, "2024-01-15 10:00"),
        _make_trade("NVDA", 5, 400, "2024-01-22 10:00"),
    ]
    mistakes = detect_overtrading(trades)
    assert len(mistakes) == 0


def test_detect_concentration():
    positions = [
        Position(symbol="AAPL", quantity=100, cost_basis_price=150, market_price=150,
                 unrealized_pnl=0, as_of_date=date(2024, 1, 15)),
        Position(symbol="NVDA", quantity=10, cost_basis_price=400, market_price=400,
                 unrealized_pnl=0, as_of_date=date(2024, 1, 15)),
    ]
    # AAPL = 15000, NVDA = 4000, total = 19000, AAPL = 78.9%
    mistakes = detect_concentration(positions)
    assert len(mistakes) >= 1
    assert mistakes[0].symbol == "AAPL"


def test_detect_concentration_balanced():
    positions = [
        Position(symbol="AAPL", quantity=10, cost_basis_price=150, market_price=150,
                 unrealized_pnl=0, as_of_date=date(2024, 1, 15)),
        Position(symbol="NVDA", quantity=10, cost_basis_price=150, market_price=150,
                 unrealized_pnl=0, as_of_date=date(2024, 1, 15)),
        Position(symbol="TSLA", quantity=10, cost_basis_price=150, market_price=150,
                 unrealized_pnl=0, as_of_date=date(2024, 1, 15)),
        Position(symbol="GOOG", quantity=10, cost_basis_price=150, market_price=150,
                 unrealized_pnl=0, as_of_date=date(2024, 1, 15)),
    ]
    mistakes = detect_concentration(positions)
    assert len(mistakes) == 0
