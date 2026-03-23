from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from whylosemoney.models import Position, Trade


@dataclass
class MistakeInstance:
    type: str
    severity: str  # high / medium / low
    symbol: str
    date: date
    description: str
    impact_amount: float = 0.0


def detect_chasing(trades: list[Trade], price_df: pd.DataFrame) -> list[MistakeInstance]:
    """Detect buying after stock rose >10% in prior 5 days."""
    mistakes: list[MistakeInstance] = []
    if price_df.empty:
        return mistakes

    for t in trades:
        if t.quantity <= 0:
            continue
        sym_prices = price_df[price_df["symbol"] == t.symbol] if "symbol" in price_df.columns else price_df
        if sym_prices.empty:
            continue

        trade_date = t.datetime.date() if hasattr(t.datetime, "date") else t.datetime
        idx = sym_prices.index
        if hasattr(idx[0], "date"):
            dates = [d.date() for d in idx]
        else:
            dates = list(idx)

        # Find price 5 business days before
        before_dates = [d for d in dates if d < trade_date]
        if len(before_dates) < 5:
            continue
        price_5d_ago = float(sym_prices.iloc[dates.index(before_dates[-5])]["close"])
        price_now = float(sym_prices.iloc[dates.index(before_dates[-1])]["close"]) if before_dates[-1] in dates else t.price
        if price_5d_ago > 0 and (price_now - price_5d_ago) / price_5d_ago > 0.10:
            gain_pct = (price_now - price_5d_ago) / price_5d_ago * 100
            mistakes.append(MistakeInstance(
                type="追高买入",
                severity="high",
                symbol=t.symbol,
                date=trade_date,
                description=f"{t.symbol} 在买入前5天已上涨 {gain_pct:.1f}%，可能是追高",
                impact_amount=0.0,
            ))
    return mistakes


def detect_overtrading(trades: list[Trade]) -> list[MistakeInstance]:
    """Detect >5 trades/week or >20 trades/month."""
    mistakes: list[MistakeInstance] = []

    # Weekly check
    weekly: dict[str, int] = defaultdict(int)
    for t in trades:
        dt = t.datetime
        week_start = dt.date() - timedelta(days=dt.weekday())
        weekly[week_start.isoformat()] += 1
    for week, count in weekly.items():
        if count > 5:
            mistakes.append(MistakeInstance(
                type="频繁交易",
                severity="medium",
                symbol="ALL",
                date=date.fromisoformat(week),
                description=f"本周交易 {count} 次（>5次），频繁交易增加手续费损耗",
            ))

    # Monthly check
    monthly: dict[str, int] = defaultdict(int)
    for t in trades:
        month_key = t.datetime.strftime("%Y-%m")
        monthly[month_key] += 1
    for month, count in monthly.items():
        if count > 20:
            mistakes.append(MistakeInstance(
                type="频繁交易",
                severity="high",
                symbol="ALL",
                date=date.fromisoformat(month + "-01"),
                description=f"{month} 月交易 {count} 次（>20次），过度交易严重侵蚀利润",
            ))
    return mistakes


def detect_concentration(positions: list[Position]) -> list[MistakeInstance]:
    """Detect single stock >30% of portfolio value."""
    mistakes: list[MistakeInstance] = []
    total_value = sum(abs(p.quantity * p.market_price) for p in positions)
    if total_value <= 0:
        return mistakes

    for p in positions:
        pos_value = abs(p.quantity * p.market_price)
        pct = pos_value / total_value * 100
        if pct > 30:
            mistakes.append(MistakeInstance(
                type="仓位过于集中",
                severity="high",
                symbol=p.symbol,
                date=p.as_of_date,
                description=f"{p.symbol} 占总仓位 {pct:.1f}%（>30%），风险过于集中",
                impact_amount=pos_value,
            ))
    return mistakes


def detect_no_stop_loss(trades: list[Trade], price_df: pd.DataFrame) -> list[MistakeInstance]:
    """Detect holding at >20% loss from buy price."""
    mistakes: list[MistakeInstance] = []
    if price_df.empty:
        return mistakes

    # Track open positions from trades
    open_buys: dict[str, list[tuple[float, date]]] = defaultdict(list)
    sorted_trades = sorted(trades, key=lambda t: t.datetime)

    for t in sorted_trades:
        td = t.datetime.date() if hasattr(t.datetime, "date") else t.datetime
        if t.quantity > 0:
            open_buys[t.symbol].append((t.price, td))
        elif t.quantity < 0 and open_buys[t.symbol]:
            sell_qty = abs(t.quantity)
            while sell_qty > 0 and open_buys[t.symbol]:
                open_buys[t.symbol].pop(0)
                sell_qty -= 1  # simplified

    for symbol, buys in open_buys.items():
        sym_prices = price_df[price_df["symbol"] == symbol] if "symbol" in price_df.columns else price_df
        if sym_prices.empty:
            continue
        latest_close = float(sym_prices.iloc[-1]["close"])
        for buy_price, buy_date in buys:
            if buy_price > 0:
                loss_pct = (latest_close - buy_price) / buy_price * 100
                if loss_pct < -20:
                    mistakes.append(MistakeInstance(
                        type="没有止损",
                        severity="high",
                        symbol=symbol,
                        date=buy_date,
                        description=f"{symbol} 买入价 ${buy_price:.2f}，当前跌 {loss_pct:.1f}%，未设止损",
                        impact_amount=(latest_close - buy_price) * 1,  # per share
                    ))
    return mistakes


def detect_counter_trend(trades: list[Trade], price_df: pd.DataFrame) -> list[MistakeInstance]:
    """Detect buying when both MA20 and MA50 are declining."""
    mistakes: list[MistakeInstance] = []
    if price_df.empty:
        return mistakes

    for t in trades:
        if t.quantity <= 0:
            continue
        sym_prices = price_df[price_df["symbol"] == t.symbol] if "symbol" in price_df.columns else price_df
        if len(sym_prices) < 50:
            continue

        close = sym_prices["close"].astype(float)
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()

        trade_date = t.datetime.date() if hasattr(t.datetime, "date") else t.datetime
        idx = sym_prices.index
        if hasattr(idx[0], "date"):
            dates = [d.date() for d in idx]
        else:
            dates = list(idx)

        closest = [d for d in dates if d <= trade_date]
        if len(closest) < 2:
            continue
        i = dates.index(closest[-1])
        if i < 1:
            continue

        ma20_declining = ma20.iloc[i] < ma20.iloc[i - 1] if pd.notna(ma20.iloc[i]) and pd.notna(ma20.iloc[i - 1]) else False
        ma50_declining = ma50.iloc[i] < ma50.iloc[i - 1] if pd.notna(ma50.iloc[i]) and pd.notna(ma50.iloc[i - 1]) else False

        if ma20_declining and ma50_declining:
            mistakes.append(MistakeInstance(
                type="逆势操作",
                severity="medium",
                symbol=t.symbol,
                date=trade_date,
                description=f"{t.symbol} 买入时 MA20 和 MA50 均下行，属于逆势操作",
            ))
    return mistakes


def run_all_detections(
    trades: list[Trade],
    positions: list[Position],
    price_df: pd.DataFrame,
) -> list[MistakeInstance]:
    all_mistakes: list[MistakeInstance] = []
    all_mistakes.extend(detect_chasing(trades, price_df))
    all_mistakes.extend(detect_overtrading(trades))
    all_mistakes.extend(detect_concentration(positions))
    all_mistakes.extend(detect_no_stop_loss(trades, price_df))
    all_mistakes.extend(detect_counter_trend(trades, price_df))
    return sorted(all_mistakes, key=lambda m: m.date)
