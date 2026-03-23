from __future__ import annotations

from pathlib import Path

from whylosemoney.chat.gemini import extract_tickers, parse_text_chat


def test_parse_text_chat_extracts_messages(tmp_path: Path) -> None:
    sample = "\n".join(
        [
            "[2024-01-15 10:30] user: Bought $NVDA after earnings",
            "[2024-01-16 09:15] friend: AAPL looks strong but IT IS expensive",
            "this line should be ignored",
        ]
    )
    chat_path = tmp_path / "chat.txt"
    chat_path.write_text(sample, encoding="utf-8")

    messages = parse_text_chat(chat_path)

    assert len(messages) == 2
    assert messages[0].source == "user"
    assert messages[0].content == "Bought $NVDA after earnings"
    assert messages[0].mentioned_tickers == ["NVDA"]
    assert messages[1].source == "friend"
    assert messages[1].mentioned_tickers == ["AAPL"]


def test_extract_tickers_filters_common_words_and_deduplicates() -> None:
    text = "Watching $AAPL, NVDA and TSLA. I AM IN IT, but NVDA still looks stronger."

    tickers = extract_tickers(text)

    assert tickers == ["AAPL", "NVDA", "TSLA"]
