from __future__ import annotations

from datetime import datetime

import pandas as pd

from whylosemoney.app.components.charts import (
    candlestick_with_trades,
    cumulative_pnl_chart,
    monthly_pnl_heatmap,
    position_pie_chart,
    stock_pnl_bar_chart,
)


def test_cumulative_pnl_chart_builds_positive_and_negative_traces() -> None:
    trades_df = pd.DataFrame(
        {
            "datetime": [
                datetime(2024, 1, 1, 9, 30),
                datetime(2024, 1, 2, 9, 30),
                datetime(2024, 1, 3, 9, 30),
            ],
            "realized_pnl": [-100.0, 25.0, 125.0],
        }
    )

    fig = cumulative_pnl_chart(trades_df)

    assert len(fig.data) == 2
    assert list(fig.data[0].x) == list(trades_df["datetime"])
    assert list(fig.data[1].x) == list(trades_df["datetime"])
    assert fig.layout.title.text == "Cumulative Realized PnL"


def test_stock_pnl_bar_chart_limits_to_top_n_by_absolute_value() -> None:
    pnl_df = pd.DataFrame(
        {
            "symbol": ["A", "B", "C", "D"],
            "pnl": [10.0, -50.0, 30.0, -5.0],
        }
    )

    fig = stock_pnl_bar_chart(pnl_df, top_n=2)

    assert list(fig.data[0].y) == ["B", "C"]
    assert list(fig.data[0].x) == [-50.0, 30.0]


def test_position_pie_chart_computes_market_value_when_missing() -> None:
    positions_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT"],
            "quantity": [2.0, 1.0],
            "market_price": [100.0, 200.0],
        }
    )

    fig = position_pie_chart(positions_df)

    assert list(fig.data[0].labels) == ["AAPL", "MSFT"]
    assert list(fig.data[0].values) == [200.0, 200.0]


def test_candlestick_with_trades_adds_buy_and_sell_markers() -> None:
    price_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL"],
            "date": [datetime(2024, 1, 1), datetime(2024, 1, 2)],
            "open": [100.0, 102.0],
            "high": [105.0, 106.0],
            "low": [99.0, 101.0],
            "close": [104.0, 103.0],
        }
    )
    trades_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "AAPL", "MSFT"],
            "datetime": [
                datetime(2024, 1, 1, 10, 0),
                datetime(2024, 1, 2, 10, 0),
                datetime(2024, 1, 1, 10, 0),
            ],
            "price": [101.0, 103.0, 300.0],
            "quantity": [10.0, -5.0, 1.0],
        }
    )

    fig = candlestick_with_trades(price_df, trades_df, "AAPL")

    assert fig.data[0].type == "candlestick"
    assert {trace.name for trace in fig.data[1:]} == {"Buy", "Sell"}


def test_monthly_pnl_heatmap_accepts_long_format() -> None:
    monthly_df = pd.DataFrame(
        {
            "year": [2024, 2024, 2025],
            "month": ["Jan", "Feb", 1],
            "return": [1.5, -2.0, 3.0],
        }
    )

    fig = monthly_pnl_heatmap(monthly_df)

    assert fig.data[0].type == "heatmap"
    assert list(fig.data[0].x[:2]) == ["Jan", "Feb"]
    assert list(fig.data[0].y) == [2024, 2025]
