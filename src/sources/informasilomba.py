"""informasilomba.com adapter (WordPress, sitemap driven)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from bs4 import BeautifulSoup

from src.config import DEADLINE_GRACE_DAYS
from src.llm import LLMExtractor
from src.models import CompetitionRecord
from src.normalizer import is_expired, normalize_url
from src.sources.article import ArticleScraper
from src.sources.base import BaseScraper

log = logging.getLogger("compScraper-v2")

BASE_URL = "https://www.informasilomba.com"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
WIB = timezone(timedelta(hours=7))


class InformasilombaScraper(ArticleScraper, BaseScraper):
    source_id = "informasilomba"
    source_name = "Informasi Lomba (informasilomba.com)"
    own_domain = "informasilomba.com"

    def __init__(self) -> None:
        BaseScraper.__init__(self)
        self.llm = LLMExtractor()

    def _sitemaps(self) -> list[str]:
        html = self.get_text(SITEMAP_URL)
        if not html:
            return []
        soup = BeautifulSoup(html, "xml")
        return [tag.get_text(strip=True) for tag in soup.find_all("loc")]

    def _urls(self, sitemap_url: str) -> list[str]:
        html = self.get_text(sitemap_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "xml")
        return [tag.get_text(strip=True) for tag in soup.find_all("loc")]

    def scrape(self, limit: int, known_urls: set[str] | None = None) -> list[CompetitionRecord]:
        known_urls = set(known_urls or ())
        records: list[CompetitionRecord] = []
        seen: set[str] = set()

        for sitemap in self._sitemaps():
            if len(records) >= limit:
                break
            for url in self._urls(sitemap):
                if len(records) >= limit:
                    break
                if url in seen or normalize_url(url) in known_urls:
                    continue
                seen.add(url)

                self.polite_sleep()
                article = self.fetch_article(url)
                if not article:
                    continue
                record = self.build_record(article, f"{self.source_id}_{len(seen)}")
                if is_expired(record.deadline, DEADLINE_GRACE_DAYS):
                    continue
                records.append(record)
                log.info("[%s] %s", record.school or "?", record.title[:70])
        return records
