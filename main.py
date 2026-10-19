#!/usr/bin/env python3
"""Lomba Aggregator & Validator Pipeline (Cakrawala University) - v2

Two-stage scraping engine for infolomba.id:
1. Discovery: SSR listing scan for event_id and seo_slug via regex onclick.
2. Deep Scrape: AJAX POST to /load-details returning JSON { "html": "..." }.
3. Classification: 6 School keyword matching (SEN, SBE, SCD, SPE, SLA, UMUM) + secondary logging.
4. Anti-Leak Dedup: GSheets DRAFT + ARCHIVE tab snapshot (preserves Rejected records).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# Asia/Jakarta = UTC+7
WIB = timezone(timedelta(hours=7))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s WIB] [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger("compScraper-v2")

BASE_URL = "https://infolomba.id"
FILTERED_LIST_URL = (
    "https://infolomba.id/events"
    "?sort=Default&title=&peserta=5"
    "&lokasi=Semua+Lokasi&kategori=Semua+Kategori"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

# Rule-based Keyword Matrix (PRD Section 6.4)
PRIORITY = ["SLA", "SPE", "SCD", "SBE", "SEN", "UMUM"]
KEYWORDS: dict[str, list[str]] = {
    "SLA": ["moot court", "hukum", "debat hukum", "esai hukum", "legal"],
    "SPE": ["psikologi", "pendidikan", "guru", "kesehatan mental", "teaching", "edukasi"],
    "SCD": [
        "desain grafis", "poster", "film", "fotografi", "jurnalistik",
        "komunikasi", "ui/ux", "videografi", "animasi", "broadcast"
    ],
    "SBE": [
        "business plan", "bisnis", "entrepreneur", "investasi", "akuntansi",
        "manajemen", "case competition", "marketing", "keuangan", "finansial"
    ],
    "SEN": [
        "programming", "coding", "machine learning", "artificial intelligence",
        "robotik", "iot", "hackathon", "data science", "elektronika",
        "software", "web development", "cyber security", "informatika"
    ],
    "UMUM": ["keagamaan", "mtq", "olahraga", "e-sports", "esai", "puisi", "karya tulis"]
}

HEADERS = [
    "Scraped At", "Judul Lomba", "Penyelenggara", "Rekomendasi School",
    "Biaya Pendaftaran", "Deadline", "Link Sumber", "Link Pendaftaran",
    "Link Guidebook", "Status Review"
]


def normalize_url(url: str | None) -> str:
    """Strip query tracking parameters, lowercase host, strip trailing slash."""
    if not url or url.strip() == "-" or not url.startswith("http"):
        return "-"
    try:
        parsed = urlparse(url.strip())
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        clean = urlunparse((parsed.scheme.lower(), netloc, path, "", "", ""))
        return clean or "-"
    except Exception:
        return url.strip()


def normalize_text(text: str | None, fallback: str = "-") -> str:
    if not text:
        return fallback
    clean = re.sub(r"\s+", " ", text).strip()
    return clean if clean else fallback


def parse_date_id(date_str: str | None) -> str:
    """Parse Indonesian/standard date strings to YYYY-MM-DD or return '-'."""
    if not date_str:
        return "-"
    clean = date_str.lower().strip()
    if "-" in clean and not re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
        clean = clean.split("-")[-1].strip()

    months = {
        "januari": "01", "jan": "01",
        "februari": "02", "feb": "02",
        "maret": "03", "mar": "03",
        "april": "04", "apr": "04",
        "mei": "05", "may": "05",
        "juni": "06", "jun": "06",
        "juli": "07", "jul": "07",
        "agustus": "08", "agu": "08", "agt": "08",
        "september": "09", "sep": "09",
        "oktober": "10", "okt": "10",
        "november": "11", "nov": "11",
        "desember": "12", "des": "12",
    }
    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", clean)
    if iso_match:
        y, m, d = iso_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    text_match = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", clean)
    if text_match:
        d, m_name, y = text_match.groups()
        m = months.get(m_name[:3]) or months.get(m_name)
        if m:
            return f"{int(y):04d}-{m}-{int(d):02d}"

    slash_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", clean)
    if slash_match:
        d, m, y = slash_match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"

    return "-"


def classify_school(title: str, description: str) -> tuple[str, list[str]]:
    """Determine primary school (highest score + priority tie-break) and secondary schools."""
    title_l = title.lower()
    desc_l = description.lower()
    scores: dict[str, int] = {}

    for school, words in KEYWORDS.items():
        score = 0
        for w in words:
            pattern = rf"\b{re.escape(w)}\b"
            if re.search(pattern, title_l):
                score += 2
            elif re.search(pattern, desc_l):
                score += 1
        scores[school] = score

    matched = [(school, score) for school, score in scores.items() if score > 0]
    if not matched:
        return "UMUM", []

    matched.sort(key=lambda x: (x[1], -PRIORITY.index(x[0])), reverse=True)
    primary = matched[0][0]
    secondaries = [s for s, _ in matched[1:] if s != "UMUM"]
    return primary, secondaries


class InfolombaV2Scraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })

    def polite_sleep(self, min_s: float = 2.0, max_s: float = 3.0):
        time.sleep(random.uniform(min_s, max_s))

    def discover_events(self, max_items: int = 15) -> list[dict[str, str]]:
        """Stage A: Discovery from SSR list page."""
        logger.info("Discovery Stage: Fetching %s", FILTERED_LIST_URL)
        resp = self.session.get(FILTERED_LIST_URL, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        cards = soup.select(".event-container") or soup.find_all("div", class_=re.compile("event-container", re.I))

        discovered: list[dict[str, str]] = []
        for card in cards:
            if len(discovered) >= max_items:
                break
            a_tag = card.find("a", onclick=True)
            if not a_tag:
                continue

            # loadDetailsEvent(2128, 'info-business-plan...', this)
            match = re.search(r"loadDetailsEvent\((\d+),\s*['\"]([^'\"]+)['\"]", a_tag["onclick"])
            if not match:
                continue

            event_id, seo_slug = match.groups()
            date_el = card.select_one(".tanggal")
            raw_date = date_el.get_text(strip=True) if date_el else ""

            discovered.append({
                "event_id": event_id,
                "seo_slug": seo_slug,
                "raw_date": raw_date,
            })

        logger.info("Discovered %d events matching Mahasiswa filter.", len(discovered))
        return discovered

    def deep_scrape_detail(self, event_id: str, seo_slug: str, fallback_date: str = "") -> dict[str, Any] | None:
        """Stage B: Deep Scrape via AJAX POST /load-details."""
        self.polite_sleep(2.0, 3.0)
        url = f"{BASE_URL}/load-details"
        headers = self.session.headers.copy()
        headers.update({
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": BASE_URL,
            "Referer": FILTERED_LIST_URL,
            "User-Agent": random.choice(USER_AGENTS),
        })

        payload = {"event_id": event_id}
        try:
            resp = self.session.post(url, data=payload, headers=headers, timeout=15)
            if resp.status_code != 200:
                logger.warning("AJAX /load-details failed for event_id %s (HTTP %s)", event_id, resp.status_code)
                return None

            json_resp = resp.json()
            html_payload = json_resp.get("html", "")
            if not html_payload:
                return None

            soup = BeautifulSoup(html_payload, "lxml")
            title_el = soup.select_one(".event-title") or soup.find(["h1", "h2", "h3"])
            title = normalize_text(title_el.get_text(strip=True) if title_el else "")

            penyelenggara_el = soup.select_one(".penyelenggara span:last-child") or soup.select_one(".penyelenggara")
            organizer = normalize_text(penyelenggara_el.get_text(strip=True) if penyelenggara_el else "", fallback="Hubungi Penyelenggara")

            biaya_el = soup.select_one(".biaya")
            fee = normalize_text(biaya_el.get_text(strip=True) if biaya_el else "", fallback="Hubungi Penyelenggara")

            desc_el = soup.select_one(".description-body") or soup.find("div", class_=re.compile("desc|content", re.I)) or soup.body
            desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

            # Canonical public URL (Column G)
            canonical_url = f"{BASE_URL}/{seo_slug}-{event_id}"

            # Deadline extraction from detail or fallback card date
            dl_match = re.search(r"(?:deadline|batas pendaftaran|terakhir|sampai)\s*[:\-]?\s*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4}|[0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{4})", desc_text, re.I)
            raw_dl = dl_match.group(1) if dl_match else fallback_date
            deadline = parse_date_id(raw_dl)

            # External links inside description
            reg_url = "-"
            guide_url = "-"
            if desc_el:
                for a in desc_el.find_all("a", href=True):
                    href = a["href"].strip()
                    if not href.startswith("http") or "infolomba.id" in href:
                        continue
                    if re.search(r"bit\.ly|forms|daftar|regist|linktr|typeform", href, re.I) and reg_url == "-":
                        reg_url = href
                    elif re.search(r"drive\.google|guide|panduan|\.pdf|dropbox", href, re.I) and guide_url == "-":
                        guide_url = href

            primary_school, secondary_schools = classify_school(title, desc_text)
            if secondary_schools:
                logger.info("Multi-School detected: '%s' -> Primary: %s | Secondary: %s", title[:45], primary_school, secondary_schools)

            scraped_at = datetime.now(WIB).strftime("%d/%m/%Y %H:%M")
            return {
                "Scraped At": scraped_at,
                "Judul Lomba": title,
                "Penyelenggara": organizer,
                "Rekomendasi School": primary_school,
                "Biaya Pendaftaran": fee,
                "Deadline": deadline,
                "Link Sumber": normalize_url(canonical_url),
                "Link Pendaftaran": normalize_url(reg_url),
                "Link Guidebook": normalize_url(guide_url),
                "Status Review": "Pending",
            }
        except Exception as exc:
            logger.error("Deep scrape exception for event_id %s: %s", event_id, exc)
            return None


class SheetsDeduplicator:
    """Anti-Leak Deduplicator backed by Google Sheets DRAFT and ARCHIVE tabs."""

    def __init__(self, sheet_id: str, creds_json: str | None = None):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        if creds_json and os.path.exists(creds_json):
            creds = Credentials.from_service_account_file(creds_json, scopes=scopes)
        elif creds_json and creds_json.strip().startswith("{"):
            info = json.loads(creds_json)
            creds = Credentials.from_service_account_info(info, scopes=scopes)
        else:
            raise ValueError("Invalid service account credentials provided.")

        client = gspread.authorize(creds)
        self.doc = client.open_by_key(sheet_id)
        self.seen_urls: set[str] = set()
        self.seen_titles: set[str] = set()
        self.draft_sheet = self._ensure_draft_sheet()
        self._load_all_existing_data()

    def _ensure_draft_sheet(self):
        try:
            ws = self.doc.worksheet("DRAFT")
        except Exception:
            try:
                ws = self.doc.worksheet("Draft")
            except Exception:
                ws = self.doc.add_worksheet(title="DRAFT", rows=1000, cols=10)
        rows = ws.get_all_values()
        if not rows or rows[0] != HEADERS:
            if not rows:
                ws.append_row(HEADERS, value_input_option="RAW")
            elif len(rows[0]) != len(HEADERS):
                logger.warning("Header mismatch detected in DRAFT sheet.")
        return ws

    def _load_all_existing_data(self):
        """Anti-Bocor: Read all rows across DRAFT and ARCHIVE regardless of review status."""
        tabs_to_check = ["DRAFT", "Draft", "ARCHIVE", "Archive"]
        for tab_name in tabs_to_check:
            try:
                ws = self.doc.worksheet(tab_name)
                records = ws.get_all_values()
                if len(records) <= 1:
                    continue
                # Column G: Link Sumber (idx 6), Column B: Judul (idx 1)
                for r in records[1:]:
                    if len(r) > 6:
                        norm_u = normalize_url(r[6])
                        if norm_u != "-":
                            self.seen_urls.add(norm_u)
                    if len(r) > 1:
                        norm_t = re.sub(r"\W+", "", r[1].lower())
                        if norm_t:
                            self.seen_titles.add(norm_t)
                logger.info("Loaded dedup snapshot from tab '%s'. Total URLs cached: %d", tab_name, len(self.seen_urls))
            except Exception:
                continue

    def filter_new(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        fresh: list[dict[str, Any]] = []
        for it in items:
            link = it.get("Link Sumber", "-")
            title = re.sub(r"\W+", "", it.get("Judul Lomba", "").lower())

            if link != "-" and link in self.seen_urls:
                logger.info("Duplicate link skipped (Anti-Leak): %s", link)
                continue
            if link == "-" and title in self.seen_titles:
                logger.info("Duplicate title skipped: %s", it.get("Judul Lomba"))
                continue

            fresh.append(it)
            if link != "-":
                self.seen_urls.add(link)
            if title:
                self.seen_titles.add(title)
        return fresh

    def append_rows(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 0
        rows = [[it.get(col, "-") for col in HEADERS] for it in items]
        self.draft_sheet.append_rows(rows, value_input_option="RAW")
        return len(rows)


def main():
    parser = argparse.ArgumentParser(description="Lomba Aggregator & Validator System v2")
    parser.add_argument("--dry-run", action="store_true", help="Scrape & classify without writing to GSheets")
    parser.add_argument("--limit", type=int, default=5, help="Number of items to scrape (default: 5)")
    args = parser.parse_args()

    start_time = time.time()
    logger.info("Pipeline v2 started (Dry-run=%s, Limit=%d)", args.dry_run, args.limit)

    engine = InfolombaV2Scraper()
    discovered = engine.discover_events(max_items=args.limit)

    items: list[dict[str, Any]] = []
    for ev in discovered:
        detail = engine.deep_scrape_detail(
            event_id=ev["event_id"],
            seo_slug=ev["seo_slug"],
            fallback_date=ev["raw_date"]
        )
        if detail:
            items.append(detail)

    logger.info("Total successfully parsed items: %d", len(items))

    if args.dry_run:
        print(json.dumps(items, indent=2, ensure_ascii=False))
        logger.info("Dry-run complete. %d items processed in %.2fs", len(items), time.time() - start_time)
        return

    sheet_id = os.getenv("SHEET_ID")
    # Support credentials.json file or env var
    creds = os.getenv("GSPREAD_SERVICE_ACCOUNT_JSON") or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not creds and os.path.exists("credentials.json"):
        creds = "credentials.json"

    if not sheet_id or not creds:
        logger.error("Missing SHEET_ID or Google Service Account credentials (file or env var).")
        sys.exit(1)

    deduper = SheetsDeduplicator(sheet_id=sheet_id, creds_json=creds)
    fresh_items = deduper.filter_new(items)
    written_count = deduper.append_rows(fresh_items)

    logger.info("Summary: Discovered=%d, Parsed=%d, Duplicates=%d, Written=%d, Elapsed=%.2fs",
                len(discovered), len(items), len(items) - len(fresh_items), written_count, time.time() - start_time)


if __name__ == "__main__":
    main()
