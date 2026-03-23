from __future__ import annotations

from datetime import date
from typing import Any, Optional

from whylosemoney.models import Position

try:
    from ib_insync import IB
except ImportError as exc:  # pragma: no cover - exercised via tests with monkeypatch
    IB = None
    _IB_IMPORT_ERROR: Optional[ImportError] = exc
else:
    _IB_IMPORT_ERROR = None


_ACCOUNT_TAG_MAP = {
    "NetLiquidation": "net_liquidation",
    "TotalCashValue": "cash",
    "SettledCash": "settled_cash",
    "BuyingPower": "buying_power",
    "ExcessLiquidity": "excess_liquidity",
    "EquityWithLoanValue": "equity_with_loan_value",
    "GrossPositionValue": "gross_position_value",
    "UnrealizedPnL": "unrealized_pnl",
    "RealizedPnL": "realized_pnl",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_summary_value(value: Any) -> Any:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


class IBKRLive:
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1) -> None:
        self.host = host
        self.port = port
        self.client_id = client_id
        self._ib = IB() if IB is not None else None
        self._account: Optional[str] = None
        self._import_error = _IB_IMPORT_ERROR

    def connect(self) -> bool:
        if self._ib is None:
            return False

        try:
            self._ib.connect(self.host, self.port, clientId=self.client_id)
            if not self._ib.isConnected():
                return False

            accounts = list(self._ib.managedAccounts() or [])
            if accounts:
                self._account = accounts[0]
            return True
        except Exception:
            return False

    def get_positions(self) -> list[Position]:
        if self._ib is None or not self._ib.isConnected():
            return []

        today = date.today()

        try:
            portfolio_items = self._ib.portfolio(self._account) if self._account else self._ib.portfolio()
        except Exception:
            portfolio_items = []

        positions = []
        for item in portfolio_items:
            contract = getattr(item, "contract", None)
            symbol = getattr(contract, "symbol", "") or getattr(item, "symbol", "")
            if not symbol:
                continue

            positions.append(
                Position(
                    symbol=str(symbol),
                    quantity=_safe_float(getattr(item, "position", 0.0)),
                    cost_basis_price=_safe_float(getattr(item, "averageCost", 0.0)),
                    market_price=_safe_float(getattr(item, "marketPrice", 0.0)),
                    unrealized_pnl=_safe_float(getattr(item, "unrealizedPNL", 0.0)),
                    as_of_date=today,
                )
            )

        return positions

    def get_account_summary(self) -> dict[str, Any]:
        if self._ib is None or not self._ib.isConnected():
            return {}

        try:
            summary_items = self._ib.accountSummary(self._account) if self._account else self._ib.accountSummary()
        except Exception:
            return {}

        summary: dict[str, Any] = {}
        for item in summary_items:
            tag = getattr(item, "tag", None)
            if not tag:
                continue

            key = _ACCOUNT_TAG_MAP.get(tag, str(tag))
            if key in summary:
                continue

            value = getattr(item, "value", None)
            summary[key] = _coerce_summary_value(value)

        return summary

    def disconnect(self) -> None:
        if self._ib is None:
            return

        try:
            if self._ib.isConnected():
                self._ib.disconnect()
        except Exception:
            return
