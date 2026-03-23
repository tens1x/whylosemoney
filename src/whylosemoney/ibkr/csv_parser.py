from __future__ import annotations

import csv
import io
from datetime import datetime
from pathlib import Path
from typing import Union

from whylosemoney.models import CashTransaction, Trade

# Transaction types that represent stock trades
TRADE_TYPES = {"买", "卖", "buy", "sell"}
# Transaction types for cash transactions
DIVIDEND_TYPES = {"股息", "dividends"}
TAX_TYPES = {"外国预扣税", "withholding tax"}
FEE_TYPES = {"其它费用", "other fees"}
DEPOSIT_TYPES = {"存款", "deposit", "电子资金转账"}
# Types to skip entirely
SKIP_TYPES = {"外汇交易组成部分", "调整", "fx translation"}


def _safe_float(val: str, default: float = 0.0) -> float:
    if not val or val == "-":
        return default
    try:
        return float(val.replace(",", ""))
    except (ValueError, TypeError):
        return default


def _parse_date(date_str: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-%m-%d, %H:%M:%S", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(date_str.strip())


def parse_csv(
    file_path_or_bytes: Union[str, Path, bytes, io.BytesIO],
) -> dict[str, list]:
    if isinstance(file_path_or_bytes, (str, Path)):
        with open(file_path_or_bytes, "r", encoding="utf-8-sig") as f:
            content = f.read()
    elif isinstance(file_path_or_bytes, bytes):
        content = file_path_or_bytes.decode("utf-8-sig")
    else:
        content = file_path_or_bytes.read().decode("utf-8-sig")

    trades: list[Trade] = []
    cash_transactions: list[CashTransaction] = []

    reader = csv.reader(io.StringIO(content))
    header_map: dict[str, int] = {}

    for row in reader:
        if len(row) < 3:
            continue

        section = row[0].strip()
        row_type = row[1].strip()

        if section != "Transaction History":
            continue

        if row_type == "Header":
            # Build column index from header row
            for i, col in enumerate(row):
                header_map[col.strip()] = i
            continue

        if row_type != "Data":
            continue

        if not header_map:
            continue

        def get(name: str, default: str = "") -> str:
            idx = header_map.get(name)
            if idx is None or idx >= len(row):
                return default
            return row[idx].strip()

        tx_type = get("交易类型") or get("Type")
        tx_type_lower = tx_type.lower()

        # Skip FX, adjustments
        if tx_type in SKIP_TYPES or tx_type_lower in {"fx translation", "fx components"}:
            continue

        date_str = get("日期") or get("Date")
        if not date_str:
            continue

        try:
            dt = _parse_date(date_str)
        except Exception:
            continue

        symbol = get("代码") or get("Symbol") or get("Code")
        description = get("说明") or get("Description")

        # Stock trades
        if tx_type in TRADE_TYPES or tx_type_lower in {"buy", "sell"}:
            if not symbol or symbol == "-":
                continue
            quantity = _safe_float(get("数量") or get("Quantity"))
            price = _safe_float(get("价格") or get("Price"))
            proceeds = _safe_float(get("总额") or get("Amount") or get("Proceeds"))
            commission = _safe_float(get("佣金") or get("Commission"))

            # Normalize: buy = positive qty, sell = negative qty
            if tx_type in {"卖", "sell"} and quantity > 0:
                quantity = -quantity

            # Fix symbol: "BRK B" -> "BRK.B"
            symbol = symbol.replace(" ", ".")

            trades.append(Trade(
                symbol=symbol,
                datetime=dt,
                quantity=quantity,
                price=price,
                proceeds=proceeds,
                commission=commission,
                realized_pnl=0.0,  # CSV doesn't provide this directly
                currency=get("Price Currency") or "USD",
                asset_category="STK",
            ))

        # Dividends
        elif tx_type in DIVIDEND_TYPES or tx_type_lower in {"dividends", "dividend"}:
            amount = _safe_float(get("总额") or get("Amount") or get("净额") or get("Net"))
            cash_transactions.append(CashTransaction(
                symbol=symbol if symbol and symbol != "-" else None,
                datetime=dt,
                amount=amount,
                type="dividend",
            ))

        # Withholding tax
        elif tx_type in TAX_TYPES or tx_type_lower in {"withholding tax"}:
            amount = _safe_float(get("总额") or get("Amount") or get("净额") or get("Net"))
            cash_transactions.append(CashTransaction(
                symbol=symbol if symbol and symbol != "-" else None,
                datetime=dt,
                amount=amount,
                type="fee",
            ))

        # Other fees
        elif tx_type in FEE_TYPES or tx_type_lower in {"other fees"}:
            amount = _safe_float(get("总额") or get("Amount") or get("净额") or get("Net"))
            cash_transactions.append(CashTransaction(
                symbol=None,
                datetime=dt,
                amount=amount,
                type="fee",
            ))

        # Deposits/Withdrawals
        elif tx_type in DEPOSIT_TYPES or tx_type_lower in {"deposit", "withdrawal", "electronic fund transfer"}:
            amount = _safe_float(get("总额") or get("Amount") or get("净额") or get("Net"))
            tx_sub = "deposit" if amount >= 0 else "withdrawal"
            cash_transactions.append(CashTransaction(
                symbol=None,
                datetime=dt,
                amount=amount,
                type=tx_sub,
            ))

    return {
        "trades": trades,
        "positions": [],  # CSV transaction history doesn't include positions
        "cash_transactions": cash_transactions,
    }
