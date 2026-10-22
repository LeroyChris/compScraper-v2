"""infolombait.com adapter (WordPress).

Listing pages are paginated with Blogger-style `?updated-max=<timestamp>`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from src.config import DEADLINE_GRACE_DAYS
from src.llm import LLMExtractor
from src.models import CompetitionRecord
from src.normalizer import is_expired, normalize_url
from src.sources.article import ArticleScraper
from src.sources.base import BaseScraper

log = logging.getLogger("compScraper-v2")

BASE_URL = "https://www.infolombait.com"
WIB = timezone(timedelta(hours=7))


class InfolombaitScraper(ArticleScraper, BaseScraper):
    source_id = "infolombait"
    source_name = "Info Lomba Ita (infolombait.com)"
    own_domain = "infolombait.com"

    def __init__(self) -> None:
        BaseScraper.__init__(self)
        self.llm = LLMExtractor()

    def _list_page(self, url: str) -> list[dict]:
        html = self.get_text(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "lxml")
        entries = []
        for article in soup.select("article"):
            anchor = article.select_one("h2.entry-title a") or article.find("a", href=True)
            if not anchor:
                continue
            time_tag = article.select_one("abbr.published.timeago")
            entries.append(
                {
                    "title": anchor.get_text(strip=True),
                    "url": anchor["href"],
                    "updated": time_tag["title"] if time_tag and time_tag.has_attr("title") else None,
                }
            )
        return entries

    def scrape(self, limit: int, known_urls: set[str] | None = None) -> list[CompetitionRecord]:
        known_urls = set(known_urls or ())
        records: list[CompetitionRecord] = []
        seen: set[str] = set()
        next_url = BASE_URL

        for page in range(1, 6):
            if len(records) >= limit:
                break
            entries = self._list_page(next_url)
            if not entries:
                break

            for entry in entries:
                if len(records) >= limit:
                    break
                url = entry["url"]
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

            last = entries[-1].get("updated")
            if not last:
                break
            next_url = (
                f"{BASE_URL}/search?updated-max={quote_plus(last)}"
                f"&max-results=6#PageNo={page + 1}"
            )
        return records
