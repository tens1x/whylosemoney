from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import create_engine, func, inspect, select

from whylosemoney.db import get_session, init_db, upsert_positions, upsert_trades
from whylosemoney.models import Position, Trade


def make_trade() -> Trade:
    return Trade(
        symbol="AAPL",
        datetime=datetime(2024, 1, 15, 9, 30, 0),
        quantity=100.0,
        price=150.0,
        proceeds=-15000.0,
        commission=-1.0,
        realized_pnl=0.0,
        currency="USD",
        asset_category="STK",
    )


def test_init_db_creates_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")

    init_db(engine)

    table_names = set(inspect(engine).get_table_names())
    assert {"trades", "positions", "cash_transactions"} <= table_names


def test_upsert_trades_inserts_and_deduplicates() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    init_db(engine)

    with get_session(engine) as session:
        first_inserted = upsert_trades(session, [make_trade()])
        second_inserted = upsert_trades(session, [make_trade()])
        trade_count = session.scalar(select(func.count()).select_from(Trade))

    assert first_inserted == 1
    assert second_inserted == 0
    assert trade_count == 1


def test_upsert_positions_works() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    init_db(engine)

    original = Position(
        symbol="NVDA",
        quantity=50.0,
        cost_basis_price=400.0,
        market_price=420.0,
        unrealized_pnl=1000.0,
        as_of_date=date(2024, 3, 31),
    )
    updated = Position(
        symbol="NVDA",
        quantity=60.0,
        cost_basis_price=405.0,
        market_price=430.0,
        unrealized_pnl=1500.0,
        as_of_date=date(2024, 3, 31),
    )

    with get_session(engine) as session:
        first_inserted = upsert_positions(session, [original])
        second_inserted = upsert_positions(session, [updated])
        stored = session.execute(
            select(Position).where(
                Position.symbol == "NVDA",
                Position.as_of_date == date(2024, 3, 31),
            )
        ).scalar_one()
        # Read attributes before session closes
        qty = stored.quantity
        cost = stored.cost_basis_price
        mkt = stored.market_price
        upnl = stored.unrealized_pnl

    assert first_inserted == 1
    assert second_inserted == 0
    assert qty == 60.0
    assert cost == 405.0
    assert mkt == 430.0
    assert upnl == 1500.0

