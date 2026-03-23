from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd

from whylosemoney.models import ChatMessage, NewsEvent, Trade


def _trade_action(quantity: float) -> str:
    return "买入" if quantity >= 0 else "卖出"

def _build_price_lookup(price_df: pd.DataFrame) -> dict[tuple[str | None, date], float]:
    if price_df.empty:
        return {}

    normalized = price_df.copy()
    if "datetime" in normalized.columns and "date" not in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["datetime"]).dt.date
    elif "date" in normalized.columns:
        normalized["date"] = pd.to_datetime(normalized["date"]).dt.date
    elif isinstance(normalized.index, pd.DatetimeIndex):
        normalized = normalized.reset_index().rename(columns={normalized.index.name or "index": "date"})
        normalized["date"] = pd.to_datetime(normalized["date"]).dt.date
    else:
        return {}

    symbol_column = "symbol" if "symbol" in normalized.columns else None
    if "close" not in normalized.columns:
        return {}

    lookup: dict[tuple[str | None, date], float] = {}
    for _, row in normalized.iterrows():
        symbol = str(row[symbol_column]).upper() if symbol_column and pd.notna(row[symbol_column]) else None
        lookup[(symbol, row["date"])] = float(row["close"])
    return lookup


def build_event_timeline(
    trades: list[Trade],
    news_events: list[NewsEvent],
    chat_messages: list[ChatMessage],
    price_df: pd.DataFrame,
) -> pd.DataFrame:
    price_lookup = _build_price_lookup(price_df)
    rows: list[dict[str, Any]] = []

    for trade in trades:
        event_date = trade.datetime.date()
        rows.append(
            {
                "datetime": trade.datetime,
                "type": "trade",
                "symbol": trade.symbol,
                "description": f"{_trade_action(trade.quantity)} {trade.symbol} {abs(trade.quantity):g} 股 @ {trade.price:.2f}",
                "details": {
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "realized_pnl": trade.realized_pnl,
                    "close_on_day": price_lookup.get((trade.symbol.upper(), event_date)),
                },
            }
        )

    for event in news_events:
        event_date = event.datetime.date()
        rows.append(
            {
                "datetime": event.datetime,
                "type": "news",
                "symbol": event.symbol,
                "description": event.headline,
                "details": {
                    "source": event.source,
                    "url": event.url,
                    "close_on_day": price_lookup.get((event.symbol.upper(), event_date)),
                },
            }
        )

    for chat in chat_messages:
        mentioned = [
            str(ticker).upper()
            for ticker in (chat.mentioned_tickers or [])
            if str(ticker).strip()
        ]
        event_symbols = mentioned or [None]
        for symbol in event_symbols:
            rows.append(
                {
                    "datetime": chat.datetime,
                    "type": "chat",
                    "symbol": symbol,
                    "description": chat.content[:120],
                    "details": {
                        "source": chat.source,
                        "content": chat.content,
                        "mentioned_tickers": mentioned,
                        "close_on_day": price_lookup.get((symbol, chat.datetime.date())),
                    },
                }
            )

    timeline = pd.DataFrame(rows, columns=["datetime", "type", "symbol", "description", "details"])
    if timeline.empty:
        return timeline

    return timeline.sort_values("datetime").reset_index(drop=True)


def generate_trade_narrative(
    trade: Trade,
    nearby_news: list[NewsEvent],
    nearby_chats: list[ChatMessage],
    price_before: float | None,
    price_after: float | None,
) -> str:
    action = _trade_action(trade.quantity)
    symbol = trade.symbol.upper()

    chat_reason = ""
    for chat in nearby_chats:
        content = chat.content.strip()
        if not content:
            continue
        chat_reason = f"群聊提到“{content[:24]}”"
        break

    news_followup = ""
    for event in nearby_news:
        headline = event.headline.strip()
        if not headline:
            continue
        delta_days = (event.datetime.date() - trade.datetime.date()).days
        if delta_days == 0:
            news_followup = f"当天出现新闻“{headline[:24]}”"
        elif delta_days > 0:
            news_followup = f"{delta_days}天后出现新闻“{headline[:24]}”"
        else:
            news_followup = f"{abs(delta_days)}天前已有新闻“{headline[:24]}”"
        break

    outcome = "后续走势不明"
    if price_before not in (None, 0) and price_after is not None:
        raw_move = (price_after - price_before) / price_before * 100
        signed_move = raw_move if trade.quantity >= 0 else -raw_move
        result_label = "盈利" if signed_move >= 0 else "亏损"
        outcome = f"{result_label}{abs(signed_move):.1f}%"

    parts = [f"{action}{symbol}"]
    if chat_reason:
        parts.append(f"因为{chat_reason}")
    if news_followup:
        parts.append(f"-> {news_followup}")
    parts.append(f"-> {outcome}")

    return " ".join(parts)
