from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from whylosemoney.models import Position


def render_positions(engine: Engine) -> None:
    st.header("💼 持仓分析")

    with Session(engine) as session:
        positions = session.execute(select(Position)).scalars().all()

        if not positions:
            st.info("暂无持仓数据。")
            return

        # Position table
        data = []
        total_value = 0.0
        for p in positions:
            mkt_value = p.quantity * p.market_price
            total_value += abs(mkt_value)
            data.append({
                "股票": p.symbol,
                "数量": p.quantity,
                "成本价": p.cost_basis_price,
                "市价": p.market_price,
                "市值": mkt_value,
                "未实现盈亏": p.unrealized_pnl,
                "盈亏%": ((p.market_price - p.cost_basis_price) / p.cost_basis_price * 100)
                if p.cost_basis_price else 0,
            })

        df = pd.DataFrame(data)

        st.dataframe(
            df.style.applymap(
                lambda v: "color: green" if isinstance(v, (int, float)) and v > 0
                else "color: red" if isinstance(v, (int, float)) and v < 0 else "",
                subset=["未实现盈亏", "盈亏%"],
            ).format({
                "成本价": "${:.2f}",
                "市价": "${:.2f}",
                "市值": "${:,.2f}",
                "未实现盈亏": "${:,.2f}",
                "盈亏%": "{:.1f}%",
            }),
            use_container_width=True,
        )

        # Pie chart
        st.subheader("仓位分布")
        pie_df = df[["股票", "市值"]].copy()
        pie_df["市值"] = pie_df["市值"].abs()
        fig = px.pie(pie_df, values="市值", names="股票", title="持仓配置")
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)

        # Concentration warning
        if total_value > 0:
            for _, row in df.iterrows():
                pct = abs(row["市值"]) / total_value * 100
                if pct > 30:
                    st.warning(f"⚠️ {row['股票']} 占总仓位 {pct:.1f}%，仓位过于集中（>30%）！")
