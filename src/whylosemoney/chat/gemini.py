from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from whylosemoney.models import ChatMessage

_COMMON_UPPER_WORDS = {
    "A",
    "AN",
    "AND",
    "AM",
    "ARE",
    "AS",
    "AT",
    "BE",
    "BUT",
    "BY",
    "DO",
    "FOR",
    "GO",
    "HE",
    "I",
    "IF",
    "IN",
    "IS",
    "IT",
    "ME",
    "NO",
    "OF",
    "ON",
    "OR",
    "SO",
    "TO",
    "UP",
    "US",
    "WE",
}
_DOLLAR_TICKER_RE = re.compile(r"(?<!\w)\$([A-Z]{2,5})(?![A-Z])")
_PLAIN_TICKER_RE = re.compile(r"\b([A-Z]{2,5})\b")
_TEXT_CHAT_LINE_RE = re.compile(
    r"^\[(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s*(?P<source>[^:]+):\s*(?P<content>.+)$"
)


def _read_input(file_path_or_bytes: str | Path | bytes) -> str:
    if isinstance(file_path_or_bytes, bytes):
        return file_path_or_bytes.decode("utf-8")

    if isinstance(file_path_or_bytes, Path):
        return file_path_or_bytes.read_text(encoding="utf-8")

    if "\n" in file_path_or_bytes or file_path_or_bytes.lstrip().startswith(("{", "[")):
        return file_path_or_bytes

    try:
        path = Path(file_path_or_bytes)
    except OSError:
        return file_path_or_bytes
    if path.exists():
        return path.read_text(encoding="utf-8")

    return file_path_or_bytes


def _parse_timestamp(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        timestamp = float(value)
        if timestamp > 1_000_000_000_000:
            timestamp /= 1000.0
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)

    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None

    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _extract_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        parts = [_extract_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("text", "content", "value", "message"):
            if key in value:
                return _extract_text(value[key])
        return ""
    return str(value).strip()


def extract_tickers(text: str) -> list[str]:
    matches: list[str] = []
    seen: set[str] = set()

    for pattern in (_DOLLAR_TICKER_RE, _PLAIN_TICKER_RE):
        for match in pattern.finditer(text):
            ticker = match.group(1).upper()
            if ticker in _COMMON_UPPER_WORDS or ticker in seen:
                continue
            seen.add(ticker)
            matches.append(ticker)

    return matches


def parse_gemini_export(file_path_or_bytes: str | Path | bytes) -> list[ChatMessage]:
    raw = _read_input(file_path_or_bytes)
    payload = json.loads(raw)
    messages = payload.get("messages", []) if isinstance(payload, dict) else []

    parsed_messages: list[ChatMessage] = []
    for item in messages:
        if not isinstance(item, dict):
            continue

        content = _extract_text(item.get("text"))
        timestamp = _parse_timestamp(item.get("timestamp"))
        if not content or timestamp is None:
            continue

        source = str(item.get("author") or item.get("role") or "gemini").strip() or "gemini"
        parsed_messages.append(
            ChatMessage(
                source=source,
                datetime=timestamp,
                content=content,
                mentioned_tickers=extract_tickers(content) or None,
                sentiment=None,
            )
        )

    parsed_messages.sort(key=lambda message: message.datetime)
    return parsed_messages


def parse_text_chat(file_path_or_bytes: str | Path | bytes) -> list[ChatMessage]:
    raw = _read_input(file_path_or_bytes)

    parsed_messages: list[ChatMessage] = []
    for line in raw.splitlines():
        match = _TEXT_CHAT_LINE_RE.match(line.strip())
        if match is None:
            continue

        timestamp = datetime.strptime(match.group("timestamp"), "%Y-%m-%d %H:%M")
        source = match.group("source").strip() or "text_chat"
        content = match.group("content").strip()
        if not content:
            continue

        parsed_messages.append(
            ChatMessage(
                source=source,
                datetime=timestamp,
                content=content,
                mentioned_tickers=extract_tickers(content) or None,
                sentiment=None,
            )
        )

    parsed_messages.sort(key=lambda message: message.datetime)
    return parsed_messages


def parse_pasted_chat(text: str) -> list[ChatMessage]:
    """Parse pasted chat text. Supports two formats:

    1. Structured: ``[YYYY-MM-DD HH:MM] source: content``
    2. Free-form: plain text treated as a single message with ticker extraction.
    """
    # Try structured format first
    messages = parse_text_chat(text)
    if messages:
        return messages

    # Fall back to free-form text: treat entire paste as one message
    text = text.strip()
    if not text:
        return []

    return [
        ChatMessage(
            source="pasted",
            datetime=datetime.now(),
            content=text,
            mentioned_tickers=extract_tickers(text) or None,
            sentiment=None,
        )
    ]
