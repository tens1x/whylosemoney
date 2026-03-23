from __future__ import annotations

from types import SimpleNamespace
from typing import Optional

from whylosemoney.ibkr import live


class FakeIB:
    def __init__(self) -> None:
        self.connected = False

    def connect(self, host: str, port: int, clientId: int) -> None:
        self.connected = True
        self.host = host
        self.port = port
        self.client_id = clientId

    def isConnected(self) -> bool:
        return self.connected

    def managedAccounts(self) -> list[str]:
        return ["DU123456"]

    def portfolio(self, account: Optional[str] = None) -> list[SimpleNamespace]:
        assert account == "DU123456"
        return [
            SimpleNamespace(
                contract=SimpleNamespace(symbol="AAPL"),
                position=10.0,
                averageCost=150.0,
                marketPrice=160.0,
                unrealizedPNL=100.0,
            )
        ]

    def accountSummary(self, account: Optional[str] = None) -> list[SimpleNamespace]:
        assert account == "DU123456"
        return [
            SimpleNamespace(tag="NetLiquidation", value="120000.50"),
            SimpleNamespace(tag="TotalCashValue", value="10000"),
        ]

    def disconnect(self) -> None:
        self.connected = False


def test_ibkrlive_returns_false_when_dependency_missing(monkeypatch) -> None:
    monkeypatch.setattr(live, "IB", None)
    monkeypatch.setattr(live, "_IB_IMPORT_ERROR", ImportError("ib_insync not installed"))

    client = live.IBKRLive()

    assert client.connect() is False
    assert client.get_positions() == []
    assert client.get_account_summary() == {}
    client.disconnect()


def test_ibkrlive_maps_portfolio_and_account_summary(monkeypatch) -> None:
    monkeypatch.setattr(live, "IB", FakeIB)
    monkeypatch.setattr(live, "_IB_IMPORT_ERROR", None)

    client = live.IBKRLive(port=4002, client_id=7)

    assert client.connect() is True

    positions = client.get_positions()
    summary = client.get_account_summary()

    assert len(positions) == 1
    assert positions[0].symbol == "AAPL"
    assert positions[0].market_price == 160.0
    assert summary["net_liquidation"] == 120000.50
    assert summary["cash"] == 10000.0

    client.disconnect()
    assert client._ib.isConnected() is False
