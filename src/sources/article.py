"""Shared behaviour for sources that expose a single article page per competition.

The page body is free-form prose, so field extraction is done by the optional
Gemini fallback and, when that is unavailable, by cheap heuristics.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.config import STALE_ARTICLE_DAYS
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
    latest_dated_event,
    split_links,
)

log = logging.getLogger("compScraper-v2")
WIB = timezone(timedelta(hours=7))

BARE_LINK_RE = re.compile(
    r"\b(?:daftar|pendaftaran|registrasi|formulir|form)\s*[:\-]?\s*"
    r"((?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s<>\"']*)?)",
    re.IGNORECASE,
)
PUB_YEAR_RE = re.compile(r"/(20\d{2})/\d{1,2}/")


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
        index = {lk["url"]: lk for lk in links}

        # Blogger/WordPress often print the registration URL as plain text.
        # Keep the preceding words as anchor text so keyword matching still works.
        known = set(index)
        for m in re.finditer(r"(https?://[^\s<>\"']+)", text):
            plain = m.group(1).rstrip(".,;:)]}\"'")
            ctx = text[max(0, m.start() - 80):m.start()].lower()
            lk = index.get(plain)
            if lk is not None:
                # A bare auto-link (text is the URL) inherits the prose before it.
                bare = not lk["text"] or lk["text"].startswith("http")
                if bare:
                    lk["text"] = ctx
                continue
            lk = {"text": ctx, "url": plain}
            links.append(lk)
            index[plain] = lk
            known.add(plain)

        # "Daftar: form.lomba.id" -- registration hosts printed without a scheme.
        for m in BARE_LINK_RE.finditer(text):
            host = m.group(1).rstrip(".,;:)]}")
            link = "https://" + host
            if link in known:
                continue
            lk = {"text": m.group(0).lower(), "url": link}
            links.append(lk)
            index[link] = lk
            known.add(link)

        return {"url": url, "title": title, "text": text, "links": links}

    def _record_id(self, url: str) -> str:
        """Stable, readable, collision-free id: source + publication month + slug."""
        m = re.search(r"/(20\d{2})/(\d{1,2})/", url)
        slug = re.sub(r"[^a-z0-9]+", "-", url.rstrip("/").rsplit("/", 1)[-1].lower()).strip("-")
        stamp = f"{m.group(1)}{m.group(2).zfill(2)}" if m else "000000"
        return f"{self.source_id}_{stamp}_{slug[:28]}"

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
            stale=self._is_stale(text, article["title"], url, deadline),
        )

    @staticmethod
    def _is_stale(text: str, title: str, url: str, deadline: str | None) -> bool:
        """True for a free-form article whose event is long over.

        Two signals: the title names a year that has passed, or the article
        carries no deadline while its latest dated moment is long gone (the year
        must match the publication year of the permalink, so an old date quoted
        inside a fresh article is ignored).
        """
        now_year = datetime.now().year
        years = [int(y) for y in re.findall(r"\b(20\d{2})\b", title or "")]
        if years and max(years) < now_year:
            return True
        if deadline:
            return False
        m = PUB_YEAR_RE.search(url)
        if not m:
            return False
        latest = latest_dated_event(text)
        if not latest or latest.year != int(m.group(1)):
            return False
        return (datetime.now().date() - latest.date()).days > STALE_ARTICLE_DAYS
