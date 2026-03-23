from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from whylosemoney.analysis.events import build_event_timeline, generate_trade_narrative
from whylosemoney.chat.gemini import extract_tickers
from whylosemoney.models import ChatMessage, NewsEvent, PriceHistory, Trade


def _load_symbols(session: Session) -> list[str]:
    symbols = {
        symbol
        for symbol in session.execute(select(Trade.symbol)).scalars()
        if symbol
    }
    symbols.update(
        symbol
        for symbol in session.execute(select(PriceHistory.symbol)).scalars()
        if symbol
    )
    symbols.update(
        symbol
        for symbol in session.execute(select(NewsEvent.symbol)).scalars()
        if symbol
    )
    return sorted({symbol.upper() for symbol in symbols})


def _message_mentions_symbol(message: ChatMessage, symbol: str) -> bool:
    mentioned = [str(item).upper() for item in (message.mentioned_tickers or [])]
    if symbol in mentioned:
        return True
    return symbol in extract_tickers(message.content)


def _filter_chats(messages: list[ChatMessage], symbol: str) -> list[ChatMessage]:
    return [message for message in messages if _message_mentions_symbol(message, symbol)]


def _price_frame(records: list[PriceHistory]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "symbol"])

    frame = pd.DataFrame(
        [
            {
                "symbol": record.symbol,
                "date": pd.Timestamp(record.date),
                "open": record.open,
                "high": record.high,
                "low": record.low,
                "close": record.close,
                "volume": record.volume,
            }
            for record in records
        ]
    )
    return frame.sort_values("date").reset_index(drop=True)


def _default_date_range(
    trades: list[Trade],
    news_events: list[NewsEvent],
    chat_messages: list[ChatMessage],
    price_records: list[PriceHistory],
) -> tuple[date, date]:
    values: list[date] = []
    values.extend(record.date for record in price_records)
    values.extend(trade.datetime.date() for trade in trades)
    values.extend(event.datetime.date() for event in news_events)
    values.extend(message.datetime.date() for message in chat_messages)
    if not values:
        today = date.today()
        return today - timedelta(days=30), today
    return min(values), max(values)


def _get_close_around(price_df: pd.DataFrame, target_dt: datetime, step: int) -> float | None:
    if price_df.empty:
        return None
    frame = price_df.sort_values("date").reset_index(drop=True)
    target_date = pd.Timestamp(target_dt.date())
    if step <= 0:
        candidates = frame.loc[frame["date"] <= target_date, "close"]
        if candidates.empty:
            return None
        return float(candidates.iloc[-1])

    candidates = frame.loc[frame["date"] >= target_date, "close"]
    if len(candidates) <= step:
        if candidates.empty:
            return None
        return float(candidates.iloc[-1])
    return float(candidates.iloc[step])


def _format_event_title(row: pd.Series) -> str:
    symbol = row["symbol"] if pd.notna(row["symbol"]) and row["symbol"] else "ALL"
    return f"{row['datetime']:%Y-%m-%d %H:%M} | {row['type']} | {symbol}"


def render_timeline(engine: Engine) -> None:
    st.subheader("事件时间线")

    with Session(engine) as session:
        symbols = _load_symbols(session)
        if not symbols:
            st.info("暂无可展示的交易、价格或新闻数据。")
            return

        selected_symbol = st.selectbox("股票", symbols)
        all_trades = list(
            session.execute(
                select(Trade).where(Trade.symbol == selected_symbol).order_by(Trade.datetime)
            ).scalars()
        )
        all_news = list(
            session.execute(
                select(NewsEvent)
                .where(NewsEvent.symbol == selected_symbol)
                .order_by(NewsEvent.datetime)
            ).scalars()
        )
        all_prices = list(
            session.execute(
                select(PriceHistory)
                .where(PriceHistory.symbol == selected_symbol)
                .order_by(PriceHistory.date)
            ).scalars()
        )
        all_chat_messages = _filter_chats(
            list(session.execute(select(ChatMessage).order_by(ChatMessage.datetime)).scalars()),
            selected_symbol,
        )

    default_start, default_end = _default_date_range(all_trades, all_news, all_chat_messages, all_prices)
    selected_range = st.date_input(
        "日期范围",
        value=(default_start, default_end),
        min_value=default_start,
        max_value=default_end,
    )
    if isinstance(selected_range, tuple):
        start_date, end_date = selected_range
    else:
        start_date = selected_range
        end_date = selected_range

    show_news = st.toggle("显示新闻", value=True)
    show_chat = st.toggle("显示聊天", value=True)
    show_trades = st.toggle("显示交易", value=True)

    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())

    trades = [trade for trade in all_trades if start_dt <= trade.datetime <= end_dt]
    news_events = [event for event in all_news if start_dt <= event.datetime <= end_dt]
    chat_messages = [message for message in all_chat_messages if start_dt <= message.datetime <= end_dt]
    price_records = [record for record in all_prices if start_date <= record.date <= end_date]
    price_df = _price_frame(price_records)

    timeline = build_event_timeline(trades, news_events, chat_messages, price_df)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.72, 0.28],
        vertical_spacing=0.06,
    )

    if not price_df.empty:
        fig.add_trace(
            go.Candlestick(
                x=price_df["date"],
                open=price_df["open"],
                high=price_df["high"],
                low=price_df["low"],
                close=price_df["close"],
                name=selected_symbol,
            ),
            row=1,
            col=1,
        )

    if show_trades and trades:
        buy_trades = [trade for trade in trades if trade.quantity >= 0]
        sell_trades = [trade for trade in trades if trade.quantity < 0]
        if buy_trades:
            fig.add_trace(
                go.Scatter(
                    x=[trade.datetime for trade in buy_trades],
                    y=[trade.price for trade in buy_trades],
                    mode="markers",
                    marker={"color": "green", "symbol": "triangle-up", "size": 12},
                    name="买入",
                    text=[f"{trade.quantity:g} 股 @ {trade.price:.2f}" for trade in buy_trades],
                ),
                row=1,
                col=1,
            )
        if sell_trades:
            fig.add_trace(
                go.Scatter(
                    x=[trade.datetime for trade in sell_trades],
                    y=[trade.price for trade in sell_trades],
                    mode="markers",
                    marker={"color": "red", "symbol": "triangle-down", "size": 12},
                    name="卖出",
                    text=[f"{abs(trade.quantity):g} 股 @ {trade.price:.2f}" for trade in sell_trades],
                ),
                row=1,
                col=1,
            )

    if show_news and news_events:
        fig.add_trace(
            go.Scatter(
                x=[event.datetime for event in news_events],
                y=[1] * len(news_events),
                mode="markers",
                marker={"color": "blue", "size": 10},
                name="新闻",
                text=[event.headline for event in news_events],
            ),
            row=2,
            col=1,
        )

    if show_chat and chat_messages:
        fig.add_trace(
            go.Scatter(
                x=[message.datetime for message in chat_messages],
                y=[0] * len(chat_messages),
                mode="markers",
                marker={"color": "orange", "size": 10},
                name="聊天",
                text=[message.content[:80] for message in chat_messages],
            ),
            row=2,
            col=1,
        )

    fig.update_yaxes(title_text="价格", row=1, col=1)
    fig.update_yaxes(
        title_text="事件",
        row=2,
        col=1,
        tickmode="array",
        tickvals=[0, 1],
        ticktext=["聊天", "新闻"],
        range=[-0.5, 1.5],
    )
    fig.update_layout(
        height=760,
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0},
        margin={"l": 20, "r": 20, "t": 40, "b": 20},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 事件明细")
    if timeline.empty:
        st.caption("当前筛选范围内没有事件。")
    else:
        visible_types: set[str] = set()
        if show_trades:
            visible_types.add("trade")
        if show_news:
            visible_types.add("news")
        if show_chat:
            visible_types.add("chat")
        visible_timeline = timeline[timeline["type"].isin(visible_types)]
        for _, row in visible_timeline.sort_values("datetime", ascending=False).iterrows():
            with st.expander(_format_event_title(row)):
                st.write(row["description"])
                st.json(row["details"])

    st.markdown("### 交易叙事分析")
    if not trades:
        st.caption("当前范围内没有交易。")
        return

    for trade in trades:
        nearby_news = [
            event
            for event in news_events
            if abs((event.datetime - trade.datetime).days) <= 2
        ]
        nearby_chats = [
            message
            for message in chat_messages
            if abs((message.datetime - trade.datetime).days) <= 2
        ]
        price_before = _get_close_around(price_df, trade.datetime, step=0)
        price_after = _get_close_around(price_df, trade.datetime, step=2)
        narrative = generate_trade_narrative(
            trade=trade,
            nearby_news=nearby_news,
            nearby_chats=nearby_chats,
            price_before=price_before,
            price_after=price_after,
        )
        st.write(f"- {narrative}")
