from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from whylosemoney.models import Trade


def compute_realized_pnl(session: Session) -> int:
    """Compute realized PnL for all sell trades using FIFO matching.

    Reads all trades from the database, groups by symbol, matches buys to
    sells in FIFO order, and updates each sell trade's realized_pnl.

    Returns the number of sell trades updated.
    """
    trades = session.execute(
        select(Trade).order_by(Trade.datetime)
    ).scalars().all()

    by_symbol: dict[str, list[Trade]] = defaultdict(list)
    for t in trades:
        by_symbol[t.symbol].append(t)

    updated = 0
    for symbol, sym_trades in by_symbol.items():
        # FIFO queue: list of (remaining_qty, buy_price)
        buys: list[list[float]] = []  # mutable [remaining_qty, buy_price]
        for t in sym_trades:
            if t.quantity > 0:
                buys.append([t.quantity, t.price])
            elif t.quantity < 0:
                sell_qty = abs(t.quantity)
                total_pnl = 0.0
                while sell_qty > 0 and buys:
                    buy_qty, buy_price = buys[0]
                    matched = min(buy_qty, sell_qty)
                    total_pnl += (t.price - buy_price) * matched
                    remaining = buy_qty - matched
                    if remaining > 1e-9:
                        buys[0][0] = remaining
                    else:
                        buys.pop(0)
                    sell_qty -= matched
                t.realized_pnl = round(total_pnl, 2)
                updated += 1

    session.flush()
    return updated


def per_stock_pnl(trades: list[Trade]) -> pd.DataFrame:
    data: dict[str, dict[str, float]] = defaultdict(lambda: {"realized_pnl": 0.0, "commission": 0.0, "trade_count": 0})
    for t in trades:
        d = data[t.symbol]
        d["realized_pnl"] += t.realized_pnl
        d["commission"] += t.commission
        d["trade_count"] += 1
    if not data:
        return pd.DataFrame(columns=["symbol", "realized_pnl", "commission", "net_pnl", "trade_count"])
    rows = []
    for sym, vals in data.items():
        rows.append({
            "symbol": sym,
            "realized_pnl": vals["realized_pnl"],
            "commission": vals["commission"],
            "net_pnl": vals["realized_pnl"] + vals["commission"],
            "trade_count": int(vals["trade_count"]),
        })
    df = pd.DataFrame(rows)
    return df.sort_values("net_pnl", ascending=True).reset_index(drop=True)


def win_loss_stats(trades: list[Trade]) -> dict[str, Any]:
    sells = [t for t in trades if t.quantity < 0 and t.realized_pnl != 0]
    if not sells:
        return {
            "win_count": 0, "loss_count": 0, "win_rate": 0.0,
            "avg_win": 0.0, "avg_loss": 0.0, "profit_factor": 0.0,
        }
    wins = [t for t in sells if t.realized_pnl > 0]
    losses = [t for t in sells if t.realized_pnl < 0]
    total_win = sum(t.realized_pnl for t in wins)
    total_loss = abs(sum(t.realized_pnl for t in losses))
    return {
        "win_count": len(wins),
        "loss_count": len(losses),
        "win_rate": len(wins) / len(sells) if sells else 0.0,
        "avg_win": total_win / len(wins) if wins else 0.0,
        "avg_loss": total_loss / len(losses) if losses else 0.0,
        "profit_factor": total_win / total_loss if total_loss > 0 else float("inf"),
    }


def holding_period_analysis(trades: list[Trade]) -> pd.DataFrame:
    by_symbol: dict[str, list[Trade]] = defaultdict(list)
    for t in sorted(trades, key=lambda x: x.datetime):
        by_symbol[t.symbol].append(t)

    round_trips = []
    for symbol, sym_trades in by_symbol.items():
        buys: list[tuple[float, float, datetime]] = []  # (remaining_qty, price, dt)
        for t in sym_trades:
            if t.quantity > 0:
                buys.append((t.quantity, t.price, t.datetime))
            elif t.quantity < 0 and buys:
                sell_qty = abs(t.quantity)
                while sell_qty > 0 and buys:
                    buy_qty, buy_price, buy_dt = buys[0]
                    matched = min(buy_qty, sell_qty)
                    holding_days = (t.datetime - buy_dt).days
                    return_pct = (t.price - buy_price) / buy_price * 100 if buy_price else 0
                    pnl = (t.price - buy_price) * matched
                    round_trips.append({
                        "symbol": symbol,
                        "buy_date": buy_dt,
                        "sell_date": t.datetime,
                        "quantity": matched,
                        "buy_price": buy_price,
                        "sell_price": t.price,
                        "holding_days": holding_days,
                        "return_pct": round(return_pct, 2),
                        "pnl": round(pnl, 2),
                    })
                    remaining = buy_qty - matched
                    if remaining > 0:
                        buys[0] = (remaining, buy_price, buy_dt)
                    else:
                        buys.pop(0)
                    sell_qty -= matched

    if not round_trips:
        return pd.DataFrame(columns=[
            "symbol", "buy_date", "sell_date", "quantity",
            "buy_price", "sell_price", "holding_days", "return_pct", "pnl",
        ])
    return pd.DataFrame(round_trips)


def monthly_pnl(trades: list[Trade]) -> pd.DataFrame:
    if not trades:
        return pd.DataFrame(columns=["month", "realized_pnl", "commission", "net_pnl"])
    data: dict[str, dict[str, float]] = defaultdict(lambda: {"realized_pnl": 0.0, "commission": 0.0})
    for t in trades:
        key = t.datetime.strftime("%Y-%m")
        data[key]["realized_pnl"] += t.realized_pnl
        data[key]["commission"] += t.commission
    rows = [
        {
            "month": k,
            "realized_pnl": v["realized_pnl"],
            "commission": v["commission"],
            "net_pnl": v["realized_pnl"] + v["commission"],
        }
        for k, v in sorted(data.items())
    ]
    return pd.DataFrame(rows)


def drawdown_analysis(trades: list[Trade]) -> dict[str, Any]:
    sorted_trades = sorted(trades, key=lambda t: t.datetime)
    if not sorted_trades:
        return {"max_drawdown": 0.0, "max_drawdown_duration_days": 0, "peak_date": None, "trough_date": None}

    cum_pnl = 0.0
    peak = 0.0
    peak_date = sorted_trades[0].datetime
    max_dd = 0.0
    max_dd_peak_date = peak_date
    max_dd_trough_date = peak_date

    for t in sorted_trades:
        cum_pnl += t.realized_pnl
        if cum_pnl > peak:
            peak = cum_pnl
            peak_date = t.datetime
        dd = peak - cum_pnl
        if dd > max_dd:
            max_dd = dd
            max_dd_peak_date = peak_date
            max_dd_trough_date = t.datetime

    duration = (max_dd_trough_date - max_dd_peak_date).days if max_dd > 0 else 0
    return {
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_duration_days": duration,
        "peak_date": max_dd_peak_date,
        "trough_date": max_dd_trough_date,
    }
