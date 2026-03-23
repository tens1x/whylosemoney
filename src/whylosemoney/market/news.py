from __future__ import annotations

import time
from datetime import date, datetime, time as dt_time, timedelta

import finnhub
from sqlalchemy import select
from sqlalchemy.orm import Session

from whylosemoney.models import NewsEvent


def _normalize_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(value).date()


def _event_key(event: NewsEvent) -> tuple[str, datetime, str, str]:
    return (event.symbol, event.datetime, event.headline, event.source)


class FinnhubNews:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = finnhub.Client(api_key=api_key)
        self.last_call_time: float | None = None
        self.min_interval_seconds = 1.0

    def _throttle(self) -> None:
        if self.last_call_time is None:
            return

        elapsed = time.monotonic() - self.last_call_time
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)

    def fetch_news(
        self,
        symbol: str,
        from_date: date | datetime | str,
        to_date: date | datetime | str,
    ) -> list[NewsEvent]:
        start_date = _normalize_date(from_date)
        end_date = _normalize_date(to_date)
        if end_date < start_date:
            return []

        self._throttle()
        payload = self.client.company_news(
            symbol,
            _from=start_date.isoformat(),
            to=end_date.isoformat(),
        )
        self.last_call_time = time.monotonic()

        events: list[NewsEvent] = []
        for item in payload or []:
            if not isinstance(item, dict):
                continue

            headline = str(item.get("headline") or "").strip()
            if not headline:
                continue

            timestamp = item.get("datetime")
            if timestamp is None:
                continue

            event_dt = datetime.fromtimestamp(int(timestamp))
            events.append(
                NewsEvent(
                    symbol=symbol.upper(),
                    datetime=event_dt,
                    headline=headline,
                    source=str(item.get("source") or "Finnhub"),
                    url=str(item.get("url") or "") or None,
                )
            )

        deduped: list[NewsEvent] = []
        seen: set[tuple[str, datetime, str, str]] = set()
        for event in sorted(events, key=lambda item: item.datetime):
            key = _event_key(event)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return deduped

    def fetch_and_cache(
        self,
        session: Session,
        symbol: str,
        from_date: date | datetime | str,
        to_date: date | datetime | str,
    ) -> list[NewsEvent]:
        normalized_symbol = symbol.upper()
        start_date = _normalize_date(from_date)
        end_date = _normalize_date(to_date)
        if end_date < start_date:
            return []

        start_dt = datetime.combine(start_date, dt_time.min)
        end_dt = datetime.combine(end_date, dt_time.max)
        cached = list(
            session.execute(
                select(NewsEvent)
                .where(
                    NewsEvent.symbol == normalized_symbol,
                    NewsEvent.datetime >= start_dt,
                    NewsEvent.datetime <= end_dt,
                )
                .order_by(NewsEvent.datetime)
            ).scalars()
        )

        missing_ranges: list[tuple[date, date]] = []
        if not cached:
            missing_ranges.append((start_date, end_date))
        else:
            cached_start = cached[0].datetime.date()
            cached_end = cached[-1].datetime.date()
            if start_date < cached_start:
                missing_ranges.append((start_date, cached_start - timedelta(days=1)))
            if end_date > cached_end:
                missing_ranges.append((cached_end + timedelta(days=1), end_date))

        existing_keys = {_event_key(event) for event in cached}
        fetched: list[NewsEvent] = []
        for range_start, range_end in missing_ranges:
            if range_end < range_start:
                continue
            for event in self.fetch_news(normalized_symbol, range_start, range_end):
                key = _event_key(event)
                if key in existing_keys:
                    continue
                existing_keys.add(key)
                session.add(event)
                fetched.append(event)

        if fetched:
            session.flush()

        combined = sorted([*cached, *fetched], key=lambda item: item.datetime)
        return combined
