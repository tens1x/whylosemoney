from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from whylosemoney.models import Position, Trade


def render_overview(engine: Engine) -> None:
    st.header("📊 投资概览")

    with Session(engine) as session:
        trades = session.execute(select(Trade).order_by(Trade.datetime)).scalars().all()
        positions = session.execute(select(Position)).scalars().all()

        if not trades:
            st.info("暂无交易数据，请先在侧边栏上传 IBKR 数据文件 (CSV 或 XML)。")
            return

        # KPI cards
        total_pnl = sum(t.realized_pnl for t in trades)
        total_commission = sum(t.commission for t in trades)
        sells = [t for t in trades if t.quantity < 0]
        sells_with_pnl = [t for t in sells if t.realized_pnl != 0]
        wins = [t for t in sells_with_pnl if t.realized_pnl > 0]
        win_rate = len(wins) / len(sells_with_pnl) * 100 if sells_with_pnl else 0

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总已实现盈亏", f"${total_pnl:,.2f}", delta_color="normal")
        c2.metric("胜率", f"{win_rate:.1f}%")
        c3.metric("总交易次数", len(trades))
        c4.metric("当前持仓数", len(positions))

        # Cumulative PnL line chart
        st.subheader("累计盈亏曲线")
        cum_data = []
        cum = 0.0
        for t in trades:
            cum += t.realized_pnl
            cum_data.append({"日期": t.datetime, "累计盈亏": cum})
        if cum_data:
            cum_df = pd.DataFrame(cum_data)
            fig = px.line(cum_df, x="日期", y="累计盈亏", title="累计已实现盈亏")
            fig.update_traces(line_color="green" if cum >= 0 else "red")
            fig.update_layout(template="plotly_dark", height=400)
            st.plotly_chart(fig, use_container_width=True)

        # Top 10 stocks by PnL
        st.subheader("按股票盈亏 (Top 10)")
        stock_pnl: dict[str, float] = {}
        for t in trades:
            stock_pnl[t.symbol] = stock_pnl.get(t.symbol, 0) + t.realized_pnl
        sorted_pnl = sorted(stock_pnl.items(), key=lambda x: x[1])
        top10 = sorted_pnl[:5] + sorted_pnl[-5:] if len(sorted_pnl) > 10 else sorted_pnl
        if top10:
            bar_df = pd.DataFrame(top10, columns=["股票", "盈亏"])
            colors = ["green" if v >= 0 else "red" for v in bar_df["盈亏"]]
            fig = go.Figure(go.Bar(
                x=bar_df["盈亏"], y=bar_df["股票"],
                orientation="h", marker_color=colors,
            ))
            fig.update_layout(template="plotly_dark", height=400, title="按股票已实现盈亏")
            st.plotly_chart(fig, use_container_width=True)

        # Current positions table
        if positions:
            st.subheader("当前持仓")
            pos_data = []
            for p in positions:
                pos_data.append({
                    "股票": p.symbol,
                    "数量": p.quantity,
                    "成本价": f"${p.cost_basis_price:.2f}",
                    "市价": f"${p.market_price:.2f}",
                    "未实现盈亏": p.unrealized_pnl,
                })
            pos_df = pd.DataFrame(pos_data)
            st.dataframe(
                pos_df.style.applymap(
                    lambda v: "color: green" if isinstance(v, (int, float)) and v > 0
                    else "color: red" if isinstance(v, (int, float)) and v < 0 else "",
                    subset=["未实现盈亏"],
                ),
                use_container_width=True,
            )
