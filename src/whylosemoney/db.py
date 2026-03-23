from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from whylosemoney.models import Base, Position, PriceHistory, Trade

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "whylosemoney.db"


def get_engine(db_path: Path | str | None = None) -> Engine:
    if db_path is None:
        db_path = DB_PATH
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(f"sqlite:///{path}", echo=False)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def get_session(engine: Engine) -> Generator[Session, None, None]:
    session = Session(engine)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def upsert_trades(session: Session, trades: list[Trade]) -> int:
    count = 0
    for t in trades:
        exists = session.execute(
            select(Trade).where(
                Trade.symbol == t.symbol,
                Trade.datetime == t.datetime,
                Trade.quantity == t.quantity,
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(t)
            count += 1
    session.flush()
    return count


def upsert_positions(session: Session, positions: list[Position]) -> int:
    count = 0
    for p in positions:
        exists = session.execute(
            select(Position).where(
                Position.symbol == p.symbol,
                Position.as_of_date == p.as_of_date,
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(p)
            count += 1
        else:
            exists.quantity = p.quantity
            exists.cost_basis_price = p.cost_basis_price
            exists.market_price = p.market_price
            exists.unrealized_pnl = p.unrealized_pnl
    session.flush()
    return count


def upsert_price_history(session: Session, records: list[PriceHistory]) -> int:
    count = 0
    for r in records:
        exists = session.execute(
            select(PriceHistory).where(
                PriceHistory.symbol == r.symbol,
                PriceHistory.date == r.date,
            )
        ).scalar_one_or_none()
        if exists is None:
            session.add(r)
            count += 1
        else:
            exists.open = r.open
            exists.high = r.high
            exists.low = r.low
            exists.close = r.close
            exists.volume = r.volume
    session.flush()
    return count
