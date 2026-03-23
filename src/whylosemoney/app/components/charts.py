from __future__ import annotations

from calendar import month_abbr, month_name
from typing import Any, Optional

import pandas as pd
import plotly.graph_objects as go

POSITIVE_COLOR = "#2ca02c"
NEGATIVE_COLOR = "#d62728"
NEUTRAL_COLOR = "#9aa0a6"

_MONTH_LOOKUP = {
    str(index): index for index in range(1, 13)
}
_MONTH_LOOKUP.update({
    month_abbr[index].lower(): index for index in range(1, 13)
})
_MONTH_LOOKUP.update({
    month_name[index].lower(): index for index in range(1, 13)
})


def _base_layout(title: str) -> dict[str, Any]:
    return {
        "template": "plotly_dark",
        "title": title,
        "margin": {"l": 32, "r": 24, "t": 56, "b": 32},
        "legend": {"orientation": "h", "yanchor": "bottom", "y": 1.02, "x": 0},
    }


def _empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        **_base_layout(title),
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "showarrow": False,
                "font": {"color": NEUTRAL_COLOR, "size": 14},
            }
        ],
    )
    return fig


def _first_present(df: pd.DataFrame, candidates: list[str], label: str) -> str:
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
    raise ValueError(f"Missing required {label} column. Expected one of: {', '.join(candidates)}")


def _coerce_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _month_to_number(value: Any) -> Optional[int]:
    if pd.isna(value):
        return None

    if isinstance(value, (int, float)):
        month = int(value)
        if 1 <= month <= 12:
            return month
        return None

    text = str(value).strip().lower()
    if text in _MONTH_LOOKUP:
        return _MONTH_LOOKUP[text]

    return None


def _monthly_matrix(monthly_df: pd.DataFrame) -> pd.DataFrame:
    if monthly_df.empty:
        return pd.DataFrame()

    if {"year", "month"} <= set(monthly_df.columns):
        value_col = _first_present(
            monthly_df,
            ["return", "returns", "monthly_return", "pnl", "realized_pnl", "value"],
            "monthly value",
        )
        data = monthly_df[["year", "month", value_col]].copy()
        data["year"] = _coerce_numeric(data["year"])
        data["month"] = data["month"].map(_month_to_number)
        data[value_col] = _coerce_numeric(data[value_col])
        data = data.dropna(subset=["year", "month"])
        if data.empty:
            return pd.DataFrame()
        pivot = data.pivot_table(index="year", columns="month", values=value_col, aggfunc="sum")
    else:
        pivot = monthly_df.copy()
        if "year" in pivot.columns:
            pivot = pivot.set_index("year")

        valid_columns = {}
        for column in pivot.columns:
            month_number = _month_to_number(column)
            if month_number is not None:
                valid_columns[column] = month_number

        if not valid_columns:
            raise ValueError("monthly_df must contain year/month columns or month-named columns")

        pivot = pivot.rename(columns=valid_columns)
        pivot = pivot.loc[:, sorted(set(valid_columns.values()))]
        pivot = pivot.apply(_coerce_numeric)

    pivot.index = pd.Index(pd.to_numeric(pivot.index, errors="coerce"), name="year")
    pivot = pivot[~pivot.index.isna()].sort_index()
    pivot = pivot.reindex(columns=list(range(1, 13)))
    pivot.columns = [month_abbr[month] for month in range(1, 13)]
    return pivot


def cumulative_pnl_chart(trades_df: pd.DataFrame) -> go.Figure:
    if trades_df.empty:
        return _empty_figure("Cumulative Realized PnL", "No trades available")

    time_col = _first_present(trades_df, ["datetime", "date"], "trade time")
    pnl_col = _first_present(trades_df, ["realized_pnl", "pnl", "realizedPnl"], "realized pnl")

    data = trades_df[[time_col, pnl_col]].copy()
    data[time_col] = pd.to_datetime(data[time_col], errors="coerce")
    data[pnl_col] = _coerce_numeric(data[pnl_col]).fillna(0.0)
    data = data.dropna(subset=[time_col]).sort_values(time_col)

    if data.empty:
        return _empty_figure("Cumulative Realized PnL", "No valid trade timestamps found")

    cumulative = data[pnl_col].cumsum()
    positive = cumulative.where(cumulative >= 0)
    negative = cumulative.where(cumulative < 0)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=data[time_col],
            y=positive,
            mode="lines",
            name="Positive",
            line={"color": POSITIVE_COLOR, "width": 3},
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=data[time_col],
            y=negative,
            mode="lines",
            name="Negative",
            line={"color": NEGATIVE_COLOR, "width": 3},
            connectgaps=False,
        )
    )
    fig.add_hline(y=0, line_dash="dot", line_color=NEUTRAL_COLOR)
    fig.update_layout(**_base_layout("Cumulative Realized PnL"))
    fig.update_xaxes(title="Date")
    fig.update_yaxes(title="PnL")
    return fig


def stock_pnl_bar_chart(pnl_df: pd.DataFrame, top_n: int = 10) -> go.Figure:
    if pnl_df.empty:
        return _empty_figure("PnL By Stock", "No PnL data available")

    symbol_col = _first_present(pnl_df, ["symbol", "ticker"], "symbol")
    pnl_col = _first_present(
        pnl_df,
        ["pnl", "realized_pnl", "total_pnl", "net_pnl", "unrealized_pnl"],
        "PnL",
    )

    data = pnl_df[[symbol_col, pnl_col]].copy()
    data[pnl_col] = _coerce_numeric(data[pnl_col]).fillna(0.0)
    data = (
        data.groupby(symbol_col, as_index=False)[pnl_col]
        .sum()
        .sort_values(pnl_col, key=lambda series: series.abs(), ascending=False)
        .head(max(int(top_n), 1))
        .sort_values(pnl_col)
    )

    colors = [POSITIVE_COLOR if value >= 0 else NEGATIVE_COLOR for value in data[pnl_col]]

    fig = go.Figure(
        go.Bar(
            x=data[pnl_col],
            y=data[symbol_col],
            orientation="h",
            marker={"color": colors},
            hovertemplate="%{y}: %{x:.2f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_dash="dot", line_color=NEUTRAL_COLOR)
    fig.update_layout(**_base_layout("PnL By Stock"), showlegend=False)
    fig.update_xaxes(title="PnL")
    fig.update_yaxes(title="Symbol")
    return fig


def position_pie_chart(positions_df: pd.DataFrame) -> go.Figure:
    if positions_df.empty:
        return _empty_figure("Position Allocation", "No positions available")

    symbol_col = _first_present(positions_df, ["symbol", "ticker"], "symbol")
    data = positions_df.copy()

    if "market_value" in data.columns:
        value_col = "market_value"
        data[value_col] = _coerce_numeric(data[value_col])
    else:
        quantity_col = _first_present(data, ["quantity", "position"], "quantity")
        price_col = _first_present(data, ["market_price", "price", "close"], "market price")
        data["market_value"] = _coerce_numeric(data[quantity_col]).fillna(0.0) * _coerce_numeric(data[price_col]).fillna(0.0)
        value_col = "market_value"

    data = data[[symbol_col, value_col]].dropna()
    data[value_col] = data[value_col].abs()
    data = data[data[value_col] > 0]

    if data.empty:
        return _empty_figure("Position Allocation", "No non-zero market values available")

    grouped = data.groupby(symbol_col, as_index=False)[value_col].sum()

    fig = go.Figure(
        go.Pie(
            labels=grouped[symbol_col],
            values=grouped[value_col],
            hole=0.35,
            sort=False,
        )
    )
    fig.update_layout(**_base_layout("Position Allocation"), showlegend=True)
    return fig


def candlestick_with_trades(
    price_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    symbol: str,
) -> go.Figure:
    if price_df.empty:
        return _empty_figure(f"{symbol} Price Action", "No price history available")

    time_col = _first_present(price_df, ["datetime", "date"], "price time")
    if "symbol" in price_df.columns:
        price_data = price_df.loc[price_df["symbol"] == symbol].copy()
    else:
        price_data = price_df.copy()

    required_price_columns = ["open", "high", "low", "close"]
    missing_price_columns = [column for column in required_price_columns if column not in price_data.columns]
    if missing_price_columns:
        raise ValueError(f"Missing required price columns: {', '.join(missing_price_columns)}")

    price_data[time_col] = pd.to_datetime(price_data[time_col], errors="coerce")
    for column in required_price_columns:
        price_data[column] = _coerce_numeric(price_data[column])
    price_data = price_data.dropna(subset=[time_col]).sort_values(time_col)

    if price_data.empty:
        return _empty_figure(f"{symbol} Price Action", "No valid price rows available")

    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=price_data[time_col],
            open=price_data["open"],
            high=price_data["high"],
            low=price_data["low"],
            close=price_data["close"],
            name=symbol,
            increasing_line_color=POSITIVE_COLOR,
            decreasing_line_color=NEGATIVE_COLOR,
        )
    )

    if not trades_df.empty:
        trade_time_col = _first_present(trades_df, ["datetime", "date"], "trade time")
        trade_price_col = _first_present(trades_df, ["price", "trade_price"], "trade price")
        quantity_col = _first_present(trades_df, ["quantity", "qty"], "trade quantity")

        if "symbol" in trades_df.columns:
            trade_data = trades_df.loc[trades_df["symbol"] == symbol].copy()
        else:
            trade_data = trades_df.copy()

        trade_data[trade_time_col] = pd.to_datetime(trade_data[trade_time_col], errors="coerce")
        trade_data[trade_price_col] = _coerce_numeric(trade_data[trade_price_col])
        trade_data[quantity_col] = _coerce_numeric(trade_data[quantity_col]).fillna(0.0)
        trade_data = trade_data.dropna(subset=[trade_time_col, trade_price_col]).sort_values(trade_time_col)

        buys = trade_data[trade_data[quantity_col] > 0]
        sells = trade_data[trade_data[quantity_col] < 0]

        if not buys.empty:
            fig.add_trace(
                go.Scatter(
                    x=buys[trade_time_col],
                    y=buys[trade_price_col],
                    mode="markers",
                    name="Buy",
                    marker={"color": POSITIVE_COLOR, "size": 11, "symbol": "triangle-up"},
                    hovertemplate="Buy %{y:.2f}<extra></extra>",
                )
            )

        if not sells.empty:
            fig.add_trace(
                go.Scatter(
                    x=sells[trade_time_col],
                    y=sells[trade_price_col],
                    mode="markers",
                    name="Sell",
                    marker={"color": NEGATIVE_COLOR, "size": 11, "symbol": "triangle-down"},
                    hovertemplate="Sell %{y:.2f}<extra></extra>",
                )
            )

    fig.update_layout(**_base_layout(f"{symbol} Price Action"))
    fig.update_xaxes(title="Date", rangeslider={"visible": False})
    fig.update_yaxes(title="Price")
    return fig


def monthly_pnl_heatmap(monthly_df: pd.DataFrame) -> go.Figure:
    matrix = _monthly_matrix(monthly_df)
    if matrix.empty:
        return _empty_figure("Monthly Returns", "No monthly return data available")

    fig = go.Figure(
        go.Heatmap(
            z=matrix.values,
            x=list(matrix.columns),
            y=[int(year) for year in matrix.index],
            colorscale=[
                [0.0, NEGATIVE_COLOR],
                [0.5, "#f0f0f0"],
                [1.0, POSITIVE_COLOR],
            ],
            zmid=0,
            colorbar={"title": "Return"},
            hovertemplate="Year %{y}, %{x}: %{z:.2f}<extra></extra>",
        )
    )
    fig.update_layout(**_base_layout("Monthly Returns"))
    fig.update_xaxes(title="Month")
    fig.update_yaxes(title="Year", type="category")
    return fig
