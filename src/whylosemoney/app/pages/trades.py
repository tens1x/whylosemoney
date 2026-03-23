from __future__ import annotations

import pandas as pd
import streamlit as st
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from whylosemoney.app.components.filters import date_range_filter, direction_filter, symbol_filter
from whylosemoney.models import Trade


def render_trades(engine: Engine) -> None:
    st.header("📋 交易历史")

    with Session(engine) as session:
        # Filters
        with st.expander("筛选条件", expanded=True):
            start, end = date_range_filter("trades")
            symbols = symbol_filter(session, "trades_sym")
            direction = direction_filter("trades_dir")

        query = select(Trade).where(Trade.datetime >= str(start), Trade.datetime <= str(end))
        if symbols:
            query = query.where(Trade.symbol.in_(symbols))
        if direction == "buy":
            query = query.where(Trade.quantity > 0)
        elif direction == "sell":
            query = query.where(Trade.quantity < 0)
        query = query.order_by(Trade.datetime.desc())

        trades = session.execute(query).scalars().all()

        if not trades:
            st.info("无符合条件的交易记录。")
            return

        data = []
        for t in trades:
            data.append({
                "日期": t.datetime.strftime("%Y-%m-%d %H:%M"),
                "股票": t.symbol,
                "方向": "买入" if t.quantity > 0 else "卖出",
                "数量": abs(t.quantity),
                "价格": f"${t.price:.2f}",
                "手续费": f"${t.commission:.2f}",
                "已实现盈亏": t.realized_pnl,
            })

        df = pd.DataFrame(data)

        st.dataframe(
            df.style.applymap(
                lambda v: "color: green" if isinstance(v, (int, float)) and v > 0
                else "color: red" if isinstance(v, (int, float)) and v < 0 else "",
                subset=["已实现盈亏"],
            ),
            use_container_width=True,
            height=600,
        )

        st.download_button(
            "📥 导出 CSV",
            df.to_csv(index=False).encode("utf-8-sig"),
            "trades.csv",
            "text/csv",
        )

        st.caption(f"共 {len(trades)} 条记录")
