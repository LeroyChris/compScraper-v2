"""Config-driven adapter for university competition portals.

A portal is described by a small config entry (list page + link pattern), so
adding another campus needs a new entry, not a new scraper class.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.config import DEADLINE_GRACE_DAYS
from src.llm import LLMExtractor
from src.models import CompetitionRecord
from src.normalizer import is_expired, normalize_url
from src.sources.article import ArticleScraper
from src.sources.base import BaseScraper

log = logging.getLogger("compScraper-v2")
WIB = timezone(timedelta(hours=7))


@dataclass
class SiteConfig:
    source_id: str
    name: str
    base_url: str
    list_url: str
    link_pattern: str
    own_domain: str


# University competition portals. Each is a self-contained event site.
SITES: list[SiteConfig] = [
    SiteConfig(
        source_id="logikaui",
        name="LOGIKA UI (FMIPA UI)",
        base_url="https://www.logikaui.id",
        list_url="https://www.logikaui.id/",
        link_pattern=r"^/competitions/",
        own_domain="logikaui.id",
    ),
]


class GenericSiteScraper(ArticleScraper, BaseScraper):
    source_id = "generic"
    source_name = "Generic portal"
    own_domain = ""

    def __init__(self, config: SiteConfig) -> None:
        BaseScraper.__init__(self)
        self.config = config
        self.source_id = config.source_id
        self.source_name = config.name
        self.own_domain = config.own_domain
        self.llm = LLMExtractor()

    def _listing(self) -> list[str]:
        html = self.get_text(self.config.list_url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        pattern = re.compile(self.config.link_pattern)
        urls: list[str] = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"]
            if pattern.search(href):
                absolute = urljoin(self.config.base_url, href)
                if absolute not in urls:
                    urls.append(absolute)
        return urls

    def scrape(self, limit: int, known_urls: set[str] | None = None) -> list[CompetitionRecord]:
        known_urls = set(known_urls or ())
        records: list[CompetitionRecord] = []
        seen: set[str] = set()

        for url in self._listing():
            if len(records) >= limit:
                break
            if url in seen or normalize_url(url) in known_urls:
                continue
            seen.add(url)

            self.polite_sleep()
            article = self.fetch_article(url)
            if not article:
                continue
            record = self.build_record(article, f"{self.source_id}_{url.rstrip('/').rsplit('/', 1)[-1]}")
            if is_expired(record.deadline, DEADLINE_GRACE_DAYS):
                continue
            records.append(record)
            log.info("[%s] %s", record.school or "?", record.title[:70])
        return records
