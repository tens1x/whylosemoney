from __future__ import annotations

import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Union

from ibflex import client, parser, Types

from whylosemoney.models import CashTransaction, Position, Trade


def _to_datetime(d: Any) -> datetime:
    if isinstance(d, datetime):
        return d
    if hasattr(d, "isoformat"):
        return datetime(d.year, d.month, d.day)
    return datetime.fromisoformat(str(d))


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_str(val: Any, default: str = "") -> str:
    if val is None:
        return default
    return str(val)


def _convert_trade(t: Any) -> Trade:
    dt = _to_datetime(getattr(t, "dateTime", None) or getattr(t, "tradeDate", None))
    return Trade(
        symbol=str(t.symbol),
        datetime=dt,
        quantity=_safe_float(t.quantity),
        price=_safe_float(t.tradePrice if hasattr(t, "tradePrice") else t.price),
        proceeds=_safe_float(getattr(t, "proceeds", 0)),
        commission=_safe_float(getattr(t, "ibCommission", 0) or getattr(t, "commission", 0)),
        realized_pnl=_safe_float(getattr(t, "fifoPnlRealized", 0) or getattr(t, "realizedPnl", 0)),
        currency=_safe_str(getattr(t, "currency", "USD"), "USD"),
        asset_category=_safe_str(getattr(t, "assetCategory", "STK"), "STK"),
    )


def _convert_position(p: Any) -> Position:
    from datetime import date as date_type

    as_of = getattr(p, "reportDate", None)
    if as_of is None:
        as_of = date_type.today()
    elif isinstance(as_of, datetime):
        as_of = as_of.date()
    elif not isinstance(as_of, date_type):
        as_of = datetime.fromisoformat(str(as_of)).date()

    return Position(
        symbol=str(p.symbol),
        quantity=_safe_float(p.position if hasattr(p, "position") else p.quantity),
        cost_basis_price=_safe_float(getattr(p, "costBasisPrice", 0)),
        market_price=_safe_float(getattr(p, "markPrice", 0) or getattr(p, "marketPrice", 0)),
        unrealized_pnl=_safe_float(getattr(p, "fifoPnlUnrealized", 0) or getattr(p, "unrealizedPnl", 0)),
        as_of_date=as_of,
    )


def _convert_cash_transaction(ct: Any) -> CashTransaction:
    dt = _to_datetime(getattr(ct, "dateTime", None) or getattr(ct, "reportDate", None))
    tx_type = _safe_str(getattr(ct, "type", ""), "other").lower()
    type_map = {
        "dividends": "dividend",
        "broker interest paid": "fee",
        "broker interest received": "fee",
        "withholding tax": "fee",
        "deposits/withdrawals": "deposit",
        "other fees": "fee",
    }
    mapped_type = type_map.get(tx_type, tx_type if tx_type else "other")

    return CashTransaction(
        symbol=_safe_str(getattr(ct, "symbol", None)) or None,
        datetime=dt,
        amount=_safe_float(ct.amount),
        type=mapped_type,
    )


def parse_flex_xml(
    file_path_or_bytes: Union[str, Path, bytes, BytesIO],
) -> dict[str, list]:
    if isinstance(file_path_or_bytes, (bytes, BytesIO)):
        raw = file_path_or_bytes if isinstance(file_path_or_bytes, bytes) else file_path_or_bytes.read()
        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        response = parser.parse(Path(tmp_path))
        Path(tmp_path).unlink(missing_ok=True)
    else:
        response = parser.parse(Path(file_path_or_bytes))

    trades: list[Trade] = []
    positions: list[Position] = []
    cash_transactions: list[CashTransaction] = []

    for stmt in response.FlexStatements:
        for t in getattr(stmt, "Trades", []) or []:
            try:
                trades.append(_convert_trade(t))
            except Exception:
                continue

        for p in getattr(stmt, "OpenPositions", []) or []:
            try:
                positions.append(_convert_position(p))
            except Exception:
                continue

        for ct in getattr(stmt, "CashTransactions", []) or []:
            try:
                cash_transactions.append(_convert_cash_transaction(ct))
            except Exception:
                continue

    return {
        "trades": trades,
        "positions": positions,
        "cash_transactions": cash_transactions,
    }
