"""infolomba.id adapter.

Listing: SSR page 0, then POST /load-event-2 with an item offset (5 per page).
Detail: POST /load-details returns the modal HTML as a JSON string.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.config import DEADLINE_GRACE_DAYS
from src.models import CompetitionRecord, sanitize_text
from src.normalizer import extract_deadline_from_text, is_expired, normalize_url, parse_indonesian_date, split_links
from src.sources.base import BaseScraper

log = logging.getLogger("compScraper-v2")

BASE_URL = "https://infolomba.id"
LIST_URL = (
    f"{BASE_URL}/events?sort=Default&title=&peserta=5"
    "&lokasi=Semua+Lokasi&kategori=Semua+Kategori"
)
PAGINATION_URL = f"{BASE_URL}/load-event-2"
DETAIL_URL = f"{BASE_URL}/load-details"
PAGE_SIZE = 5  # confirmed against /load-event-2 (event_count < 5 ends pagination)

WIB = timezone(timedelta(hours=7))
_ONCLICK_RE = re.compile(r"loadDetailsEvent\((\d+),\s*['\"]([^'\"]+)['\"]")


class InfolombaScraper(BaseScraper):
    source_id = "infolomba"
    source_name = "Info Lomba (infolomba.id)"
    own_domain = "infolomba.id"

    # -- listing --------------------------------------------------------------
    def parse_event_cards(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        events: list[dict] = []
        seen: set[str] = set()

        for card in soup.select(".event-container"):
            anchor = card.find("a", onclick=True)
            if not anchor:
                continue
            match = _ONCLICK_RE.search(str(anchor.get("onclick", "")))
            if not match:
                continue
            event_id, slug = match.groups()
            if event_id in seen:
                continue
            seen.add(event_id)

            date_el = card.select_one(".tanggal")
            raw_date = date_el.get_text(strip=True) if date_el else ""
            deadline_str, _ = parse_indonesian_date(raw_date)

            events.append(
                {
                    "event_id": event_id,
                    "seo_slug": slug,
                    "raw_date": raw_date,
                    "deadline": deadline_str,
                    "canonical": f"{BASE_URL}/{slug}-{event_id}",
                }
            )
        return events

    def fetch_list_page(self, page_index: int) -> list[dict]:
        if page_index == 0:
            html = self.get_text(LIST_URL)
            return self.parse_event_cards(html) if html else []

        start = page_index * PAGE_SIZE
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": LIST_URL,
        }
        resp = self.request(
            "POST", PAGINATION_URL,
            data={
                "start": start, "sort": "Default", "title": "", "peserta": "5",
                "lokasi": "Semua Lokasi", "kategori": "Semua Kategori",
            },
            headers=headers,
        )
        if resp is None:
            return []
        try:
            payload = resp.json()
        except ValueError:
            log.warning("Pagination page %d returned non-JSON", page_index + 1)
            return []
        return self.parse_event_cards(payload.get("html", ""))

    # -- detail ---------------------------------------------------------------
    def fetch_detail(self, event_id: str, seo_slug: str, fallback_deadline: str | None) -> CompetitionRecord | None:
        self.polite_sleep()
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": LIST_URL,
        }
        resp = self.request("POST", DETAIL_URL, data={"event_id": event_id}, headers=headers)
        if resp is None:
            return None
        try:
            html = resp.json().get("html", "")
        except ValueError:
            return None
        if not html:
            return None

        soup = BeautifulSoup(html, "lxml")

        def pick(*selectors):
            for sel in selectors:
                el = soup.select_one(sel)
                if el is not None:
                    return el
            return None

        title_el = pick(".event-title", "h1", "h2", "h3")
        title = sanitize_text(title_el.get_text(strip=True) if title_el else "", fallback=f"Event {event_id}")

        org_el = pick(".penyelenggara span:last-child", ".penyelenggara")
        organizer = sanitize_text(org_el.get_text(strip=True) if org_el else "", fallback="Hubungi Penyelenggara")

        lokasi_el = pick(".lokasi")
        location = sanitize_text(lokasi_el.get_text(" ", strip=True) if lokasi_el else "")

        biaya_el = pick(".biaya")
        fee = sanitize_text(biaya_el.get_text(" ", strip=True) if biaya_el else "")

        target_el = pick(".target")
        target = sanitize_text(target_el.get_text(" ", strip=True) if target_el else "")

        desc_el = pick(".description-body", "div.entry-content")
        description = desc_el.get_text(" ", strip=True) if desc_el else ""

        canonical = f"{BASE_URL}/{seo_slug}-{event_id}" if seo_slug else f"{BASE_URL}/{event_id}"

        links = []
        if desc_el:
            for a in desc_el.find_all("a", href=True):
                links.append({"text": a.get_text(strip=True).lower(), "url": a["href"].strip()})
        reg_url, guide_url = split_links(links, self.own_domain)

        deadline = fallback_deadline
        from_body = extract_deadline_from_text(description)
        if from_body:
            deadline = from_body
        if not deadline:
            deadline = parse_indonesian_date(fee)[0]

        return CompetitionRecord(
            id=f"{self.source_id}_{event_id}",
            source_id=self.source_id,
            title=title,
            organizer=organizer,
            location=location,
            target=target,
            fee=fee,
            deadline=deadline,
            registration_url=normalize_url(reg_url if reg_url != "-" else canonical),
            guidebook_url=normalize_url(guide_url),
            source_url=normalize_url(canonical),
            description=description,
            scraped_at=datetime.now(WIB).strftime("%d/%m/%Y %H:%M"),
        )

    # -- contract -------------------------------------------------------------
    def scrape(self, limit: int, known_urls: set[str] | None = None) -> list[CompetitionRecord]:
        known_urls = set(known_urls or ())
        records: list[CompetitionRecord] = []
        seen: set[str] = set()

        for page in range(1, 8):
            if len(records) >= limit:
                break
            events = self.fetch_list_page(page - 1)
            if not events:
                break

            for ev in events:
                if len(records) >= limit:
                    break
                event_id = ev["event_id"]
                canonical = normalize_url(ev["canonical"])
                if canonical in known_urls or event_id in seen:
                    log.info("Pre-filter: %s already known", event_id)
                    continue
                if is_expired(ev["deadline"], DEADLINE_GRACE_DAYS):
                    log.info("Pre-filter: %s expired (%s)", event_id, ev["deadline"])
                    continue

                record = self.fetch_detail(event_id, ev["seo_slug"], ev["deadline"])
                if record is None:
                    continue
                seen.add(event_id)
                records.append(record)
                log.info("[%s] %s", record.school or "?", record.title[:70])
        return records
