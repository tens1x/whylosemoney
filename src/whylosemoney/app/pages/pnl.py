from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from whylosemoney.analysis.mistakes import run_all_detections
from whylosemoney.analysis.pnl import (
    drawdown_analysis,
    holding_period_analysis,
    monthly_pnl,
    per_stock_pnl,
    win_loss_stats,
)
from whylosemoney.models import Position, Trade

MISTAKE_ADVICE = {
    "追高买入": "避免在股票短期大涨后追入。设定买入纪律：只在回调或突破确认后入场。",
    "频繁交易": "减少交易频率，每次交易前写下买入理由。手续费和滑点是隐形杀手。",
    "仓位过于集中": "单只股票不超过总仓位的20-30%。分散到5-10只不相关的标的。",
    "没有止损": "每笔交易设定止损位（如-8%到-15%），严格执行。亏小钱才能赚大钱。",
    "逆势操作": "尊重趋势，不要在均线下行时抄底。等趋势企稳再入场。",
}


def render_pnl(engine: Engine) -> None:
    st.header("📈 盈亏分析")

    with Session(engine) as session:
        trades = list(session.execute(select(Trade).order_by(Trade.datetime)).scalars().all())
        positions = list(session.execute(select(Position)).scalars().all())

        if not trades:
            st.info("暂无交易数据。")
            return

        tab1, tab2, tab3 = st.tabs(["盈亏总览", "持仓周期", "亏钱原因"])

        with tab1:
            _render_pnl_overview(trades)

        with tab2:
            _render_holding_periods(trades)

        with tab3:
            _render_mistakes(trades, positions)


def _render_pnl_overview(trades: list[Trade]) -> None:
    stats = win_loss_stats(trades)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("胜率", f"{stats['win_rate']:.1%}")
    c2.metric("平均盈利", f"${stats['avg_win']:,.2f}")
    c3.metric("平均亏损", f"${stats['avg_loss']:,.2f}")
    c4.metric("利润因子", f"{stats['profit_factor']:.2f}")

    # Per stock PnL
    stock_df = per_stock_pnl(trades)
    if not stock_df.empty:
        colors = ["green" if v >= 0 else "red" for v in stock_df["net_pnl"]]
        fig = go.Figure(go.Bar(
            x=stock_df["net_pnl"], y=stock_df["symbol"],
            orientation="h", marker_color=colors,
        ))
        fig.update_layout(template="plotly_dark", title="按股票净盈亏", height=400)
        st.plotly_chart(fig, use_container_width=True)

    # Monthly PnL
    month_df = monthly_pnl(trades)
    if not month_df.empty:
        colors = ["green" if v >= 0 else "red" for v in month_df["net_pnl"]]
        fig = go.Figure(go.Bar(x=month_df["month"], y=month_df["net_pnl"], marker_color=colors))
        fig.update_layout(template="plotly_dark", title="月度净盈亏", height=350)
        st.plotly_chart(fig, use_container_width=True)

    # Drawdown
    dd = drawdown_analysis(trades)
    if dd["max_drawdown"] > 0:
        st.metric("最大回撤", f"${dd['max_drawdown']:,.2f}",
                  delta=f"{dd['max_drawdown_duration_days']} 天", delta_color="inverse")


def _render_holding_periods(trades: list[Trade]) -> None:
    hp_df = holding_period_analysis(trades)
    if hp_df.empty:
        st.info("无完整买卖配对数据。")
        return

    fig = px.scatter(
        hp_df, x="holding_days", y="return_pct",
        color="symbol", size=hp_df["pnl"].abs(),
        hover_data=["buy_price", "sell_price", "pnl"],
        title="持仓天数 vs 收益率",
    )
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(template="plotly_dark", height=500)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(hp_df.style.format({
        "buy_price": "${:.2f}", "sell_price": "${:.2f}",
        "return_pct": "{:.1f}%", "pnl": "${:,.2f}",
    }), use_container_width=True)


def _render_mistakes(trades: list[Trade], positions: list[Position]) -> None:
    empty_df = pd.DataFrame()
    mistakes = run_all_detections(trades, positions, empty_df)

    if not mistakes:
        st.success("🎉 未检测到常见亏钱模式！继续保持！")
        return

    # Summary by type
    type_summary: dict[str, dict] = {}
    for m in mistakes:
        if m.type not in type_summary:
            type_summary[m.type] = {"count": 0, "total_impact": 0.0, "cases": []}
        type_summary[m.type]["count"] += 1
        type_summary[m.type]["total_impact"] += m.impact_amount
        type_summary[m.type]["cases"].append(m)

    for mistake_type, info in type_summary.items():
        with st.expander(f"❌ {mistake_type} — {info['count']} 次", expanded=True):
            if info["total_impact"] != 0:
                st.metric("影响金额", f"${info['total_impact']:,.2f}")

            for case in info["cases"][:10]:
                severity_color = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(case.severity, "⚪")
                st.markdown(f"{severity_color} **{case.symbol}** ({case.date}) — {case.description}")

            advice = MISTAKE_ADVICE.get(mistake_type, "")
            if advice:
                st.info(f"💡 **建议**: {advice}")
