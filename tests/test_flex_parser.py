from __future__ import annotations

from pathlib import Path

from whylosemoney.ibkr.flex_parser import parse_flex_xml


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "sample_flex.xml"


def test_parse_flex_xml_with_sample_fixture() -> None:
    parsed = parse_flex_xml(FIXTURE_PATH)

    assert len(parsed["trades"]) == 3
    assert len(parsed["positions"]) == 1
    assert len(parsed["cash_transactions"]) >= 1
    assert parsed["trades"][0].symbol == "AAPL"
