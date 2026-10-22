"""luarkampus.id adapter -- the campus event portal.

Cards are server-rendered; pagination is a plain `?page=N` query parameter.
Event detail pages require a login, so everything the audit needs is taken
from the card itself.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.config import DEADLINE_GRACE_DAYS
from src.models import CompetitionRecord, sanitize_text
from src.normalizer import is_expired, normalize_url, parse_indonesian_date, split_links
from src.sources.base import BaseScraper

log = logging.getLogger("compScraper-v2")

BASE_URL = "https://luarkampus.id"
LIST_URL = f"{BASE_URL}/events"
WIB = timezone(timedelta(hours=7))

_TARGET_BADGE_RE = re.compile(r"^(SMA|SMK|D\d|S\d|3\+|2\+|8\+|\d\+)$", re.IGNORECASE)
_FUNDED_RE = re.compile(r"fully\s*funded|gratis|free", re.IGNORECASE)


class LuarkampusScraper(BaseScraper):
    source_id = "luarkampus"
    source_name = "Luarkampus"
    own_domain = "luarkampus.id"

    def parse_cards(self, html: str) -> list[CompetitionRecord]:
        soup = BeautifulSoup(html, "lxml")
        records: list[CompetitionRecord] = []

        for anchor in soup.select('a[href*="luarkampus.id/events/"]'):
            url = anchor.get("href", "")
            event_id = url.rstrip("/").rsplit("/", 1)[-1]
            if not event_id.isdigit():
                continue

            title_el = anchor.select_one("p.font-bold") or anchor.find("p")
            title = sanitize_text(title_el.get_text(strip=True) if title_el else "", fallback="")
            if not title:
                continue

            card_text = anchor.get_text(" ", strip=True)

            organizer = "-"
            org_el = anchor.select_one("span.font-semibold.line-clamp-1")
            if org_el:
                organizer = sanitize_text(org_el.get_text(strip=True))

            level = "-"
            m = re.search(r"Tingkat\s+(.+?)(?:\s{2,}|\s+-\s+Fully|$)", card_text)
            if m:
                level = sanitize_text(m.group(1))

            fee = "GRATIS" if _FUNDED_RE.search(card_text) else "-"

            location = "-"
            loc_icon = anchor.select_one('img[src*="location"]')
            if loc_icon:
                sibling = loc_icon.find_next_sibling("span")
                if sibling:
                    location = sanitize_text(sibling.get_text(strip=True))

            deadline_raw = "-"
            start_raw = "-"
            dl_el = anchor.find(string=re.compile(r"Deadline:"))
            if dl_el:
                b = dl_el.find_next("b")
                deadline_raw = b.get_text(strip=True) if b else "-"
            st_el = anchor.find(string=re.compile(r"Mulai:"))
            if st_el:
                b = st_el.find_next("b")
                start_raw = b.get_text(strip=True) if b else "-"

            deadline, _ = parse_indonesian_date(deadline_raw)
            start, _ = parse_indonesian_date(start_raw)

            badges = []
            for span in anchor.find_all("span"):
                text = span.get_text(strip=True)
                if len(text) <= 4 and _TARGET_BADGE_RE.match(text):
                    badges.append(text.upper())

            links = [
                {"text": a.get_text(strip=True).lower(), "url": a["href"]}
                for a in anchor.find_all("a", href=True)
                if a["href"].startswith("http")
            ]
            reg_url, guide_url = split_links(links, self.own_domain)

            records.append(
                CompetitionRecord(
                    id=f"{self.source_id}_{event_id}",
                    source_id=self.source_id,
                    title=title,
                    organizer=organizer,
                    location=location,
                    target=", ".join(dict.fromkeys(badges)) or "-",
                    fee=fee,
                    deadline=deadline,
                    registration_url=normalize_url(reg_url if reg_url != "-" else url),
                    guidebook_url=normalize_url(guide_url),
                    source_url=normalize_url(url),
                    description=f"{level} | {card_text[:300]}" if level != "-" else card_text[:300],
                    scraped_at=datetime.now(WIB).strftime("%d/%m/%Y %H:%M"),
                )
            )
        return records

    def scrape(self, limit: int, known_urls: set[str] | None = None) -> list[CompetitionRecord]:
        known_urls = set(known_urls or ())
        records: list[CompetitionRecord] = []

        for page in range(1, 6):
            if len(records) >= limit:
                break
            html = self.get_text(f"{LIST_URL}?page={page}")
            if not html:
                break
            cards = self.parse_cards(html)
            if not cards:
                break
            for record in cards:
                if len(records) >= limit:
                    break
                if record.source_url in known_urls:
                    continue
                if is_expired(record.deadline, DEADLINE_GRACE_DAYS):
                    continue
                records.append(record)
                log.info("[%s] %s", record.school or "?", record.title[:70])
        return records
