from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pandas as pd
import yfinance as yf
from sqlalchemy import select
from sqlalchemy.orm import Session

from whylosemoney.db import upsert_price_history
from whylosemoney.models import PriceHistory


def _yf_ticker(symbol: str) -> str:
    """Convert IBKR ticker format to yfinance format."""
    return symbol.replace(".", "-").replace(" ", "-")


def fetch_price_history(
    symbol: str,
    start_date: date,
    end_date: date,
) -> list[PriceHistory]:
    yf_sym = _yf_ticker(symbol)
    end_plus = end_date + timedelta(days=1)
    df = yf.download(
        yf_sym,
        start=start_date.isoformat(),
        end=end_plus.isoformat(),
        progress=False,
        auto_adjust=True,
    )
    if df.empty:
        return []

    # Handle MultiIndex columns from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    records: list[PriceHistory] = []
    for idx, row in df.iterrows():
        dt = idx.date() if hasattr(idx, "date") else idx
        records.append(
            PriceHistory(
                symbol=symbol,
                date=dt,
                open=float(row["Open"]),
                high=float(row["High"]),
                low=float(row["Low"]),
                close=float(row["Close"]),
                volume=int(row["Volume"]),
            )
        )
    return records


def get_cached_prices(
    session: Session,
    symbol: str,
    start: date,
    end: date,
) -> pd.DataFrame:
    cached = session.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == symbol,
            PriceHistory.date >= start,
            PriceHistory.date <= end,
        )
        .order_by(PriceHistory.date)
    ).scalars().all()

    if cached:
        cached_dates = {r.date for r in cached}
        all_dates_covered = True
        d = start
        biz_days = 0
        while d <= end:
            if d.weekday() < 5:
                biz_days += 1
                if d not in cached_dates:
                    all_dates_covered = False
                    break
            d += timedelta(days=1)
        if all_dates_covered and biz_days > 0:
            return _records_to_df(cached)

    new_records = fetch_price_history(symbol, start, end)
    if new_records:
        upsert_price_history(session, new_records)
        session.commit()

    all_records = session.execute(
        select(PriceHistory)
        .where(
            PriceHistory.symbol == symbol,
            PriceHistory.date >= start,
            PriceHistory.date <= end,
        )
        .order_by(PriceHistory.date)
    ).scalars().all()

    return _records_to_df(all_records)


def _records_to_df(records: list[PriceHistory]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"])
    data = [
        {
            "date": r.date,
            "open": r.open,
            "high": r.high,
            "low": r.low,
            "close": r.close,
            "volume": r.volume,
            "symbol": r.symbol,
        }
        for r in records
    ]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date")
