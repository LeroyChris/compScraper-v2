"""Shared behaviour for sources that expose a single article page per competition.

The page body is free-form prose, so field extraction is done by the optional
Gemini fallback and, when that is unavailable, by cheap heuristics.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.llm import LLMExtractor
from src.models import CompetitionRecord, sanitize_text
from src.normalizer import (
    normalize_url,
    extract_deadline_from_text,
    guess_registration_deadline,
    guess_fee,
    guess_location,
    guess_organizer,
    guess_target,
    html_to_text,
    split_links,
)

log = logging.getLogger("compScraper-v2")
WIB = timezone(timedelta(hours=7))


class ArticleScraper:
    """Mixin: article fetching + record building. Expects BaseScraper semantics."""

    llm: LLMExtractor

    @staticmethod
    def _year_hint(title: str, url: str) -> int | None:
        """Event year: from the title, else from the publication path (/2026/05/)."""
        for text in (title, url):
            m = re.search(r"\b(20\d{2})\b", text or "")
            if m:
                return int(m.group(1))
        return None

    def fetch_article(self, url: str) -> dict | None:
        html = self.get_text(url)
        if not html:
            return None
        soup = BeautifulSoup(html, "lxml")

        title_el = (
            soup.select_one("h1.entry-title")
            or soup.select_one("article h1")
            or soup.select_one("h1")
            or soup.select_one("title")
        )
        title = sanitize_text(title_el.get_text(" ", strip=True) if title_el else "", fallback="")
        half = len(title) // 2
        if half and title[:half].strip() == title[half:].strip():
            title = title[:half].strip()

        content_el = (
            soup.select_one("div.entry-content")
            or soup.select_one("article")
            or soup.select_one("main")
            or soup.body
        )
        text = html_to_text(str(content_el)) if content_el else ""

        links = []
        if content_el:
            for a in content_el.find_all("a", href=True):
                links.append({"text": a.get_text(strip=True).lower(), "url": a["href"].strip()})

        # Blogger/WordPress often print the registration URL as plain text.
        for raw in re.findall(r"https?://[^\s<>\"']+", text):
            url = raw.rstrip(".,;:)]}\"'")
            if url not in {lk["url"] for lk in links}:
                links.append({"text": "", "url": url})

        return {"url": url, "title": title, "text": text, "links": links}

    def build_record(self, article: dict, record_id: str) -> CompetitionRecord:
        url = article["url"]
        text = article["text"]
        year_hint = self._year_hint(article["title"], url)

        fields = self.llm.extract(text, url) or {}
        reg_url, guide_url = split_links(article["links"], self.own_domain)

        deadline = (
            fields.get("deadline")
            or extract_deadline_from_text(text, year_hint)
            or guess_registration_deadline(text, year_hint)
        )
        fee = fields.get("fee") or guess_fee(text)
        location = fields.get("location") or guess_location(text)
        target = fields.get("target") or guess_target(text)
        organizer = fields.get("organizer") or guess_organizer(text, article["title"])
        registration = fields.get("registration_url") or reg_url

        if registration in (None, "", "-"):
            registration = url

        return CompetitionRecord(
            id=record_id,
            source_id=self.source_id,
            title=article["title"] or fields.get("title") or "-",
            organizer=organizer or "-",
            location=location or "-",
            target=target or "-",
            fee=fee or "-",
            deadline=deadline,
            registration_url=normalize_url(registration),
            guidebook_url=normalize_url(guide_url),
            source_url=normalize_url(url),
            description=(fields.get("description") or text)[:400],
            scraped_at=datetime.now(WIB).strftime("%d/%m/%Y %H:%M"),
        )
