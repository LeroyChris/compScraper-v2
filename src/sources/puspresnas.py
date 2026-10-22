"""Pusat Prestasi Nasional (puspresnas) adapter.

The portal is a Svelte/Inertia app: the full event dataset is embedded in the
`data-page` attribute as JSON, so no headless browser is needed.

ponytail: the gov.id server ships an incomplete TLS chain, so certificate
verification is disabled for this host only. Fix by installing the government
intermediate CA and flipping `insecure_ssl` to False.
"""

from __future__ import annotations

import html as html_lib
import json
import logging
import re
from datetime import datetime, timedelta, timezone

from src.config import DEADLINE_GRACE_DAYS
from src.models import CompetitionRecord, sanitize_text
from src.normalizer import html_to_text, is_expired, normalize_url
from src.sources.base import BaseScraper

log = logging.getLogger("compScraper-v2")

BASE_URL = "https://pusatprestasinasional.kemendikdasmen.go.id"
LEVELS = ["sma", "smp", "sd"]
ORGANIZER = "Pusat Prestasi Nasional (Kemendikdasmen)"
WIB = timezone(timedelta(hours=7))

_DATA_PAGE_RE = re.compile(r'data-page="([^"]+)"')
_FREE_RE = re.compile(r"\b(gratis|tanpa biaya|free)\b", re.IGNORECASE)


class PuspresnasScraper(BaseScraper):
    source_id = "puspresnas"
    source_name = "Puspresnas"
    own_domain = "pusatprestasinasional.kemendikdasmen.go.id"
    insecure_ssl = True

    def _page_payload(self, url: str) -> dict | None:
        raw = self.get_text(url)
        if not raw:
            return None
        match = _DATA_PAGE_RE.search(raw)
        if not match:
            log.warning("No data-page payload at %s", url)
            return None
        try:
            return json.loads(html_lib.unescape(match.group(1)))
        except (ValueError, json.JSONDecodeError) as exc:
            log.warning("Bad data-page JSON at %s: %s", url, exc)
            return None

    def _events(self, payload: dict) -> list[dict]:
        data = payload.get("props", {}).get("data", {})
        events: list[dict] = []
        for month in data.get("month", []) or []:
            for event in month.get("event", []) or []:
                event.setdefault("bulan", month.get("bulan"))
                events.append(event)
        return events

    def scrape(self, limit: int, known_urls: set[str] | None = None) -> list[CompetitionRecord]:
        known_urls = set(known_urls or ())
        records: list[CompetitionRecord] = []
        seen: set[str] = set()

        for level in LEVELS:
            if len(records) >= limit:
                break
            for page in range(1, 4):
                if len(records) >= limit:
                    break
                url = f"{BASE_URL}/jenjang/{level}" + (f"?page={page}" if page > 1 else "")
                payload = self._page_payload(url)
                if not payload:
                    break
                events = self._events(payload)
                if not events:
                    break

                for event in events:
                    if len(records) >= limit:
                        break
                    event_id = str(event.get("id"))
                    if event_id in seen:
                        continue

                    slug = event.get("slug") or f"event-{event_id}"
                    source_url = event.get("route") or f"{BASE_URL}/event/{slug}"
                    if source_url in known_urls:
                        continue

                    description = html_to_text(event.get("detail_singly") or event.get("detail_singkat") or event.get("detail") or "")
                    deadline = event.get("end") or None
                    if is_expired(deadline, DEADLINE_GRACE_DAYS):
                        continue

                    fee = "GRATIS" if _FREE_RE.search(description) else "-"
                    link = event.get("link") or "-"

                    records.append(
                        CompetitionRecord(
                            id=f"{self.source_id}_{event_id}",
                            source_id=self.source_id,
                            title=sanitize_text(event.get("nama_event") or event.get("nama_singkat") or ""),
                            organizer=ORGANIZER,
                            location="-",
                            target=level.upper(),
                            fee=fee,
                            deadline=deadline,
                            registration_url=normalize_url(link),
                            guidebook_url="-",
                            source_url=normalize_url(source_url),
                            description=description[:400],
                            scraped_at=datetime.now(WIB).strftime("%d/%m/%Y %H:%M"),
                        )
                    )
                    seen.add(event_id)
        return records
