from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

CONFIG_PATH = Path.home() / ".whylosemoney" / "config.json"

DEFAULT_CONFIG = {
    "finnhub_api_key": "",
    "chasing_threshold_pct": 10.0,
    "chasing_lookback_days": 5,
    "overtrading_weekly_limit": 5,
    "overtrading_monthly_limit": 20,
    "concentration_limit_pct": 30.0,
    "stop_loss_threshold_pct": 20.0,
}


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                saved = json.load(f)
            merged = {**DEFAULT_CONFIG, **saved}
            return merged
        except Exception:
            pass
    return dict(DEFAULT_CONFIG)


def _save_config(config: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def get_config() -> dict:
    if "app_config" not in st.session_state:
        st.session_state.app_config = _load_config()
    return st.session_state.app_config


def render_settings() -> None:
    st.header("Settings")

    config = get_config()

    st.subheader("API Keys")
    finnhub_key = st.text_input(
        "Finnhub API Key",
        value=config.get("finnhub_api_key", ""),
        type="password",
        help="Free tier: https://finnhub.io/register",
    )

    st.subheader("Detection Thresholds")

    col1, col2 = st.columns(2)
    with col1:
        chasing_pct = st.number_input(
            "Chasing: price rise % (5-day)",
            value=config.get("chasing_threshold_pct", 10.0),
            min_value=1.0, max_value=50.0, step=1.0,
        )
        overtrading_weekly = st.number_input(
            "Overtrading: weekly limit",
            value=int(config.get("overtrading_weekly_limit", 5)),
            min_value=1, max_value=50, step=1,
        )
        concentration_pct = st.number_input(
            "Concentration: single stock %",
            value=config.get("concentration_limit_pct", 30.0),
            min_value=5.0, max_value=80.0, step=5.0,
        )

    with col2:
        chasing_days = st.number_input(
            "Chasing: lookback days",
            value=int(config.get("chasing_lookback_days", 5)),
            min_value=1, max_value=30, step=1,
        )
        overtrading_monthly = st.number_input(
            "Overtrading: monthly limit",
            value=int(config.get("overtrading_monthly_limit", 20)),
            min_value=1, max_value=200, step=5,
        )
        stop_loss_pct = st.number_input(
            "No stop-loss: loss % threshold",
            value=config.get("stop_loss_threshold_pct", 20.0),
            min_value=5.0, max_value=50.0, step=1.0,
        )

    if st.button("Save"):
        new_config = {
            "finnhub_api_key": finnhub_key,
            "chasing_threshold_pct": chasing_pct,
            "chasing_lookback_days": int(chasing_days),
            "overtrading_weekly_limit": int(overtrading_weekly),
            "overtrading_monthly_limit": int(overtrading_monthly),
            "concentration_limit_pct": concentration_pct,
            "stop_loss_threshold_pct": stop_loss_pct,
        }
        _save_config(new_config)
        st.session_state.app_config = new_config
        st.success("Settings saved!")
