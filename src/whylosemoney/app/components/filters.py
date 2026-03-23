from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import streamlit as st
from sqlalchemy import select
from sqlalchemy.orm import Session

from whylosemoney.models import Trade


def date_range_filter(key: str = "date_range") -> tuple[date, date]:
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("开始日期", value=date.today() - timedelta(days=365), key=f"{key}_start")
    with col2:
        end = st.date_input("结束日期", value=date.today(), key=f"{key}_end")
    return start, end


def symbol_filter(session: Session, key: str = "symbols") -> list[str]:
    symbols = session.execute(
        select(Trade.symbol).distinct().order_by(Trade.symbol)
    ).scalars().all()
    if not symbols:
        return []
    selected = st.multiselect("选择股票", options=symbols, default=[], key=key)
    return selected


def direction_filter(key: str = "direction") -> Optional[str]:
    choice = st.radio("交易方向", ["全部", "买入", "卖出"], horizontal=True, key=key)
    if choice == "买入":
        return "buy"
    elif choice == "卖出":
        return "sell"
    return None
