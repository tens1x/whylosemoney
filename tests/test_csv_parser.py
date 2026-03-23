from __future__ import annotations

from whylosemoney.ibkr.csv_parser import parse_csv


SAMPLE_CSV = """\
Statement,Header,域名称,域值
Statement,Data,Title,Transaction History
Statement,Data,Period,"三月 12, 2025 - 三月 12, 2026"
总结,Header,域名称,域值
总结,Data,基础货币,USD
Transaction History,Header,日期,账户,说明,交易类型,代码,数量,价格,Price Currency,总额,佣金,净额,子类型,汇率,交易费用,乘数
Transaction History,Data,2025-07-30,U***32808,PALANTIR TECHNOLOGIES INC-A,买,PLTR,5.0,158.01,USD,-790.05,-0.34486725,-790.39486725,-,1.0,-,1.0
Transaction History,Data,2025-10-01,U***32808,PALANTIR TECHNOLOGIES INC-A,卖,PLTR,-3.0,180.96,USD,542.88,-0.34752125,542.53247875,-,1.0,-,1.0
Transaction History,Data,2025-12-26,U***32808,NVDA(US67066G1040) 现金红利 USD 0.01 每股 (常规股息),股息,NVDA,-,-,-,0.1,-,0.1,-,1.0,-,1.0
Transaction History,Data,2025-12-26,U***32808,NVDA(US67066G1040) 现金红利 USD 0.01 每股 - US 税收,外国预扣税,NVDA,-,-,-,-0.01,-,-0.01,-,1.0,-,1.0
Transaction History,Data,2025-07-25,U***32808,电子资金转账,存款,-,-,-,-,1274.0,-,1274.0,-,0.1274,-,1.0
Transaction History,Data,2025-09-30,U***32808,外汇交易基础货币净额: -2.38 USD.HKD,外汇交易组成部分,USD.HKD,-2.38,7.77734,HKD,-0.001,-,-0.001,-,0.12849,-,1.0
Transaction History,Data,2026-03-12,U***32808,FX Translations P&L,调整,-,-,-,-,-3.228,-,-3.228,-,1.0,-,1.0
""".encode("utf-8-sig")


def test_parse_csv_trades():
    result = parse_csv(SAMPLE_CSV)
    trades = result["trades"]
    assert len(trades) == 2
    assert trades[0].symbol == "PLTR"
    assert trades[0].quantity == 5.0  # buy
    assert trades[1].quantity == -3.0  # sell


def test_parse_csv_cash_transactions():
    result = parse_csv(SAMPLE_CSV)
    cash = result["cash_transactions"]
    dividends = [c for c in cash if c.type == "dividend"]
    fees = [c for c in cash if c.type == "fee"]
    deposits = [c for c in cash if c.type == "deposit"]
    assert len(dividends) == 1
    assert dividends[0].amount == 0.1
    assert len(fees) == 1  # withholding tax
    assert len(deposits) == 1


def test_parse_csv_skips_fx_and_adjustments():
    result = parse_csv(SAMPLE_CSV)
    trades = result["trades"]
    # FX components and adjustments should be skipped
    symbols = [t.symbol for t in trades]
    assert "USD.HKD" not in symbols


def test_parse_csv_real_file():
    """Test with real IBKR CSV if available."""
    from pathlib import Path
    real_file = Path.home() / "Documents" / "ibkr" / "U15132808.TRANSACTIONS.1Y.csv"
    if not real_file.exists():
        return
    result = parse_csv(real_file)
    assert len(result["trades"]) > 0
    # All trades should have valid symbols
    for t in result["trades"]:
        assert t.symbol and t.symbol != "-"
        assert t.quantity != 0
