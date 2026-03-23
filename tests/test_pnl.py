from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from whylosemoney.analysis.pnl import (
    compute_realized_pnl,
    drawdown_analysis,
    holding_period_analysis,
    monthly_pnl,
    per_stock_pnl,
    win_loss_stats,
)
from whylosemoney.models import Base, Trade


def _make_trade(symbol: str, qty: float, price: float, pnl: float = 0.0, dt: str = "2024-01-15 10:00") -> Trade:
    return Trade(
        symbol=symbol,
        datetime=datetime.fromisoformat(dt),
        quantity=qty,
        price=price,
        proceeds=qty * price,
        commission=-1.0,
        realized_pnl=pnl,
    )


def test_per_stock_pnl():
    trades = [
        _make_trade("AAPL", 100, 150, 0, "2024-01-10 10:00"),
        _make_trade("AAPL", -100, 155, 500, "2024-01-20 10:00"),
        _make_trade("NVDA", 50, 400, 0, "2024-01-15 10:00"),
        _make_trade("NVDA", -50, 380, -1000, "2024-02-01 10:00"),
    ]
    df = per_stock_pnl(trades)
    assert len(df) == 2
    aapl = df[df["symbol"] == "AAPL"].iloc[0]
    assert aapl["realized_pnl"] == 500
    nvda = df[df["symbol"] == "NVDA"].iloc[0]
    assert nvda["realized_pnl"] == -1000


def test_win_loss_stats():
    trades = [
        _make_trade("AAPL", -100, 155, 500, "2024-01-20 10:00"),
        _make_trade("NVDA", -50, 380, -1000, "2024-02-01 10:00"),
        _make_trade("TSLA", -30, 250, 300, "2024-02-05 10:00"),
    ]
    stats = win_loss_stats(trades)
    assert stats["win_count"] == 2
    assert stats["loss_count"] == 1
    assert abs(stats["win_rate"] - 2 / 3) < 0.01
    assert stats["avg_win"] == 400.0
    assert stats["avg_loss"] == 1000.0


def test_holding_period_analysis():
    trades = [
        _make_trade("AAPL", 100, 150, 0, "2024-01-10 10:00"),
        _make_trade("AAPL", -100, 160, 1000, "2024-01-20 10:00"),
    ]
    df = holding_period_analysis(trades)
    assert len(df) == 1
    assert df.iloc[0]["holding_days"] == 10
    assert df.iloc[0]["return_pct"] > 0


def test_monthly_pnl():
    trades = [
        _make_trade("AAPL", -100, 155, 500, "2024-01-20 10:00"),
        _make_trade("NVDA", -50, 380, -1000, "2024-02-01 10:00"),
    ]
    df = monthly_pnl(trades)
    assert len(df) == 2
    assert df.iloc[0]["month"] == "2024-01"


def test_drawdown_analysis():
    trades = [
        _make_trade("A", -1, 100, 100, "2024-01-01 10:00"),
        _make_trade("B", -1, 100, -300, "2024-01-05 10:00"),
        _make_trade("C", -1, 100, 50, "2024-01-10 10:00"),
    ]
    dd = drawdown_analysis(trades)
    assert dd["max_drawdown"] == 300.0  # peak 100, trough -200 (cum: 100, -200, -150)


def test_compute_realized_pnl_fifo():
    """FIFO matching: buy 100@150, buy 50@160, sell 120@170 → pnl computed correctly."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([
            Trade(symbol="AAPL", datetime=datetime(2024, 1, 10, 10, 0), quantity=100, price=150.0,
                  proceeds=15000, commission=-1.0, realized_pnl=0.0),
            Trade(symbol="AAPL", datetime=datetime(2024, 1, 12, 10, 0), quantity=50, price=160.0,
                  proceeds=8000, commission=-1.0, realized_pnl=0.0),
            Trade(symbol="AAPL", datetime=datetime(2024, 1, 20, 10, 0), quantity=-120, price=170.0,
                  proceeds=-20400, commission=-1.0, realized_pnl=0.0),
        ])
        session.commit()

    with Session(engine) as session:
        count = compute_realized_pnl(session)
        session.commit()

    assert count == 1  # one sell trade updated

    with Session(engine) as session:
        sell = session.query(Trade).filter(Trade.quantity < 0).one()
        # FIFO: 100 shares matched at buy 150 → pnl = (170-150)*100 = 2000
        #        20 shares matched at buy 160 → pnl = (170-160)*20 = 200
        # total = 2200
        assert sell.realized_pnl == 2200.0


def test_compute_realized_pnl_multiple_symbols():
    """Each symbol is matched independently."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([
            Trade(symbol="AAPL", datetime=datetime(2024, 1, 1), quantity=100, price=150.0,
                  proceeds=15000, commission=0, realized_pnl=0.0),
            Trade(symbol="AAPL", datetime=datetime(2024, 1, 10), quantity=-100, price=140.0,
                  proceeds=-14000, commission=0, realized_pnl=0.0),
            Trade(symbol="NVDA", datetime=datetime(2024, 1, 1), quantity=50, price=400.0,
                  proceeds=20000, commission=0, realized_pnl=0.0),
            Trade(symbol="NVDA", datetime=datetime(2024, 1, 10), quantity=-50, price=450.0,
                  proceeds=-22500, commission=0, realized_pnl=0.0),
        ])
        session.commit()

    with Session(engine) as session:
        count = compute_realized_pnl(session)
        session.commit()

    assert count == 2

    with Session(engine) as session:
        aapl_sell = session.query(Trade).filter(Trade.symbol == "AAPL", Trade.quantity < 0).one()
        nvda_sell = session.query(Trade).filter(Trade.symbol == "NVDA", Trade.quantity < 0).one()
        assert aapl_sell.realized_pnl == -1000.0  # (140-150)*100
        assert nvda_sell.realized_pnl == 2500.0   # (450-400)*50
