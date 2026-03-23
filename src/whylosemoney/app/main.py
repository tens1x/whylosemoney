from __future__ import annotations

import streamlit as st

from whylosemoney.db import get_engine, get_session, init_db, upsert_trades, upsert_positions
from whylosemoney.ibkr.csv_parser import parse_csv
from whylosemoney.ibkr.flex_parser import parse_flex_xml
from whylosemoney.models import CashTransaction


def main() -> None:
    st.set_page_config(page_title="WhyLoseMoney", page_icon="📉", layout="wide")

    if "engine" not in st.session_state:
        engine = get_engine()
        init_db(engine)
        st.session_state.engine = engine
        # Auto-compute PnL for any existing trades missing realized_pnl
        from whylosemoney.analysis.pnl import compute_realized_pnl
        with get_session(engine) as session:
            compute_realized_pnl(session)

    engine = st.session_state.engine

    # Sidebar
    with st.sidebar:
        st.title("📉 WhyLoseMoney")
        st.caption("搞清楚你的钱是怎么亏的")

        # Data Upload
        st.subheader("导入数据")
        data_file = st.file_uploader("上传 IBKR 数据文件", type=["csv", "xml"])
        if data_file is not None and "parsed_data" not in st.session_state:
            if st.button("解析并预览"):
                try:
                    raw = data_file.read()
                    if data_file.name.endswith(".csv"):
                        result = parse_csv(raw)
                    else:
                        result = parse_flex_xml(raw)
                    # Store parsed result immediately to avoid re-read issues
                    st.session_state.parsed_data = result
                    st.success(
                        f"解析成功: {len(result['trades'])} 笔交易, "
                        f"{len(result['positions'])} 个持仓, "
                        f"{len(result['cash_transactions'])} 笔现金流"
                    )
                except Exception as e:
                    st.error(f"解析失败: {e}")

        if "parsed_data" in st.session_state:
            st.info(
                f"已解析: {len(st.session_state.parsed_data['trades'])} 笔交易, "
                f"{len(st.session_state.parsed_data['positions'])} 个持仓"
            )
            if st.button("✅ 确认导入数据库"):
                data = st.session_state.parsed_data
                with get_session(engine) as session:
                    t_count = upsert_trades(session, data["trades"])
                    p_count = upsert_positions(session, data["positions"])
                    for ct in data["cash_transactions"]:
                        session.add(ct)
                # Compute realized PnL via FIFO after import
                from whylosemoney.analysis.pnl import compute_realized_pnl
                with get_session(engine) as session:
                    pnl_count = compute_realized_pnl(session)
                st.success(f"导入完成: {t_count} 笔新交易, {p_count} 个持仓, {pnl_count} 笔卖出已计算盈亏")
                del st.session_state.parsed_data

        # Chat input — paste text directly
        st.subheader("聊天记录")
        chat_text = st.text_area(
            "粘贴聊天文本",
            height=150,
            placeholder="粘贴 Gemini/群聊记录...\n格式: [2024-01-15 10:30] user: 买了 $NVDA\n或直接粘贴自由文本",
        )
        chat_url = st.text_input("相关链接 (可选)", placeholder="https://...")
        if chat_text and st.button("导入聊天记录"):
            try:
                from whylosemoney.chat.gemini import parse_pasted_chat
                messages = parse_pasted_chat(chat_text)
                with get_session(engine) as session:
                    for msg in messages:
                        session.add(msg)
                st.success(f"导入 {len(messages)} 条聊天记录")
            except Exception as e:
                st.error(f"导入失败: {e}")

        st.divider()
        page = st.radio("导航", ["概览", "持仓", "交易", "盈亏分析", "事件时间线", "设置"])

    # Page routing
    if page == "概览":
        from whylosemoney.app.pages.overview import render_overview
        render_overview(engine)
    elif page == "持仓":
        from whylosemoney.app.pages.positions import render_positions
        render_positions(engine)
    elif page == "交易":
        from whylosemoney.app.pages.trades import render_trades
        render_trades(engine)
    elif page == "盈亏分析":
        from whylosemoney.app.pages.pnl import render_pnl
        render_pnl(engine)
    elif page == "事件时间线":
        from whylosemoney.app.pages.timeline import render_timeline
        render_timeline(engine)
    elif page == "设置":
        from whylosemoney.app.pages.settings import render_settings
        render_settings()


if __name__ == "__main__":
    main()
