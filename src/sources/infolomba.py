"""Infolomba.id multi-page scraper with early date filtering and smart link fallbacks."""

from __future__ import annotations

import logging
import random
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.classifier import classify_school
from src.models import CompetitionItem, normalize_url, sanitize_text
from src.normalizer import parse_indonesian_date

log = logging.getLogger("compScraper-v2")

BASE_URL = "https://infolomba.id"
FILTERED_LIST_URL = (
    "https://infolomba.id/events"
    "?sort=Default&title=&peserta=5"
    "&lokasi=Semua+Lokasi&kategori=Semua+Kategori"
)
PAGINATION_URL = f"{BASE_URL}/load-event-2"
DETAIL_URL = f"{BASE_URL}/load-details"
PAGE_SIZE = 12

WIB = timezone(timedelta(hours=7))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

REG_LINK_KEYWORDS = (
    "daftar", "registrasi", "register", "registration",
    "formulir", "form", "gform", "linktr.ee", "bit.ly",
    "typeform", "s.id", "unesa.me", "ipb.link", "ugm.id",
    "docs.google.com/forms", "forms.gle", "tally.so"
)

GUIDE_LINK_KEYWORDS = (
    "panduan", "guide", "juklak", "juknis", "rulebook",
    "booklet", "pedoman", "syarat", "ketentuan", "silabus",
    "drive.google.com", "dropbox", "pdf"
)


class InfolombaScraper:
    """Scraper provider for infolomba.id with multi-page support and early filtering."""

    def __init__(self, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

    def polite_sleep(self, min_s: float = 2.0, max_s: float = 3.0):
        time.sleep(random.uniform(min_s, max_s))

    def parse_event_cards(self, html: str) -> list[dict[str, Any]]:
        """Extract event ID, slug, and deadline metadata from event cards."""
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select(".event-container") or soup.find_all("div", class_=re.compile("event-container", re.I))

        events: list[dict[str, Any]] = []
        for card in cards:
            a_tag = card.find("a", onclick=True)
            if not a_tag:
                continue

            # onclick="loadDetailsEvent(2128, 'info-business-plan...', this)"
            match = re.search(r"loadDetailsEvent\((\d+),\s*['\"]([^'\"]+)['\"]", str(a_tag))
            if not match:
                continue

            event_id, seo_slug = match.groups()
            date_el = card.select_one(".tanggal")
            raw_date = date_el.get_text(strip=True) if date_el else ""
            date_str, date_dt = parse_indonesian_date(raw_date)

            events.append({
                "event_id": str(event_id),
                "seo_slug": seo_slug,
                "raw_date": raw_date,
                "deadline_str": date_str,
                "deadline_dt": date_dt,
            })
        return events

    def fetch_list_page(self, page_index: int) -> list[dict[str, Any]]:
        """Fetch list page 0 via SSR, page >= 1 via AJAX POST /load-event-2."""
        if page_index == 0:
            log.info("Scanning list page 1 (SSR): %s", FILTERED_LIST_URL)
            resp = self.session.get(FILTERED_LIST_URL, timeout=15)
            resp.raise_for_status()
            return self.parse_event_cards(resp.text)

        offset = page_index * PAGE_SIZE
        log.info("Scanning list page %d (AJAX offset: %d)...", page_index + 1, offset)
        payload = {
            "start": offset,
            "sort": "Default",
            "title": "",
            "peserta": "5",
            "lokasi": "Semua Lokasi",
            "kategori": "Semua Kategori",
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": FILTERED_LIST_URL,
            "User-Agent": random.choice(USER_AGENTS),
        }
        resp = self.session.post(PAGINATION_URL, data=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        html_content = data.get("html", "")
        return self.parse_event_cards(html_content)

    def fetch_event_detail(
        self,
        event_id: str,
        seo_slug: str = "",
        fallback_date_str: str = "-",
    ) -> CompetitionItem | None:
        """Deep scrape via AJAX POST /load-details with link fallbacks."""
        self.polite_sleep(2.0, 3.0)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": FILTERED_LIST_URL,
            "User-Agent": random.choice(USER_AGENTS),
        }

        try:
            resp = self.session.post(DETAIL_URL, data={"event_id": event_id}, headers=headers, timeout=15)
            if resp.status_code != 200:
                log.warning("Detail failed for event_id %s (HTTP %s)", event_id, resp.status_code)
                return None

            html_payload = resp.json().get("html", "")
            if not html_payload:
                return None

            soup = BeautifulSoup(html_payload, "lxml")
            title_el = soup.select_one(".event-title") or soup.find(["h1", "h2", "h3"])
            title = sanitize_text(title_el.get_text(strip=True) if title_el else f"Event {event_id}")

            org_el = soup.select_one(".penyelenggara span:last-child") or soup.select_one(".penyelenggara")
            organizer = sanitize_text(org_el.get_text(strip=True) if org_el else "", fallback="Hubungi Penyelenggara")

            biaya_el = soup.select_one(".biaya")
            fee = sanitize_text(biaya_el.get_text(strip=True) if biaya_el else "", fallback="Hubungi Penyelenggara")

            desc_el = soup.select_one(".description-body") or soup.find("div", class_=re.compile("desc|content", re.I)) or soup.body
            desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

            canonical_url = f"{BASE_URL}/{seo_slug}-{event_id}" if seo_slug else f"{BASE_URL}/{event_id}"

            # Deadline extraction from body or fallback to card date
            dl_match = re.search(
                r"(?:deadline|batas pendaftaran|terakhir|sampai)\s*[:\-]?\s*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4}|[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})",
                desc_text,
                re.I,
            )
            deadline = fallback_date_str
            if dl_match:
                parsed_dl, _ = parse_indonesian_date(dl_match.group(1))
                if parsed_dl != "-":
                    deadline = parsed_dl

            # Smart link classification & fallbacks
            ext_links: list[dict[str, str]] = []
            if desc_el:
                for a in desc_el.find_all("a", href=True):
                    href = a["href"].strip()
                    text = a.get_text(strip=True).lower()
                    if href.startswith("http") and "infolomba.id" not in href:
                        ext_links.append({"text": text, "url": href})

            reg_url = "-"
            guide_url = "-"

            # Pass 1: Keyword-based matching
            for item in ext_links:
                u = item["url"].lower()
                t = item["text"]
                if reg_url == "-" and any(k in t or k in u for k in REG_LINK_KEYWORDS):
                    reg_url = item["url"]
                elif guide_url == "-" and any(k in t or k in u for k in GUIDE_LINK_KEYWORDS):
                    guide_url = item["url"]

            # Pass 2: Fallback to available external links to prevent '-' (zonk)
            remaining_links = [it["url"] for it in ext_links if it["url"] not in (reg_url, guide_url)]
            if reg_url == "-" and remaining_links:
                reg_url = remaining_links.pop(0)
            if guide_url == "-" and remaining_links:
                guide_url = remaining_links.pop(0)

            # Fallback for registration to canonical source if still empty
            if reg_url == "-":
                reg_url = canonical_url

            primary_school, secondary_schools = classify_school(title, desc_text)
            if secondary_schools:
                log.info("Multi-School detected: '%s' -> Primary: %s | Secondary: %s", title[:45], primary_school, secondary_schools)

            scraped_at = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
            return CompetitionItem(
                scraped_at=scraped_at,
                title=title,
                organizer=organizer,
                school=primary_school,
                fee=fee,
                deadline=deadline,
                source_url=normalize_url(canonical_url),
                registration_url=normalize_url(reg_url),
                guidebook_url=normalize_url(guide_url),
                status_review="Pending",
            )
        except Exception as exc:
            log.error("Deep scrape exception for event %s: %s", event_id, exc)
            return None

    def scrape(self, max_items: int = 20, max_pages: int = 3, existing_urls: set[str] | None = None) -> list[CompetitionItem]:
        """Scrape pipeline iterating through pages with Pre-Detail and Dedup filtering."""
        existing_urls = existing_urls or set()
        records: list[CompetitionItem] = []
        now = datetime.now()

        for page in range(max_pages):
            if len(records) >= max_items:
                break

            try:
                page_events = self.fetch_list_page(page)
            except Exception as e:
                log.error("Error fetching page %d: %s", page + 1, e)
                break

            if not page_events:
                log.info("No events found on page %d. Ending discovery.", page + 1)
                break

            for ev in page_events:
                if len(records) >= max_items:
                    break

                eid = ev["event_id"]
                slug = ev.get("seo_slug", "")
                canonical = f"{BASE_URL}/{slug}-{eid}" if slug else f"{BASE_URL}/{eid}"
                norm_canonical = normalize_url(canonical)

                # Pre-Detail Filter 1: Check existing URL dedup
                if norm_canonical in existing_urls:
                    log.info("Pre-filter: Event %s already exists in Sheet snapshot. Skipping.", eid)
                    continue

                # Pre-Detail Filter 2: Check expired date
                deadline_dt = ev.get("deadline_dt")
                if deadline_dt and deadline_dt < now:
                    log.info("Pre-filter: Event %s expired (%s). Skipping.", eid, ev["deadline_str"])
                    continue

                item = self.fetch_event_detail(
                    event_id=eid,
                    seo_slug=slug,
                    fallback_date_str=ev.get("deadline_str", "-"),
                )
                if item:
                    records.append(item)
                    existing_urls.add(item.source_url)
                    log.info("Successfully extracted [%s]: %s", item.school, item.title)

        log.info("Scraping completed. Extracted %d new items.", len(records))
        return records
