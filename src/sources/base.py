"""Base scraper: shared session, retry/backoff and polite pacing."""

from __future__ import annotations

import logging
import random
import time
from abc import ABC, abstractmethod

import requests

from src.config import MAX_DELAY_SECONDS, MAX_RETRIES, MIN_DELAY_SECONDS, TIMEOUT
from src.models import CompetitionRecord

log = logging.getLogger("compScraper-v2")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
]

RETRY_STATUS = {429, 500, 502, 503, 504}


class BaseScraper(ABC):
    source_id: str = "base"
    source_name: str = "Base"
    own_domain: str = ""
    # Some government sites ship an incomplete TLS chain; opt in explicitly.
    insecure_ssl: bool = False

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": random.choice(USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
                "Connection": "keep-alive",
            }
        )
        self.session.verify = not self.insecure_ssl

    # -- http -----------------------------------------------------------------
    def polite_sleep(self) -> None:
        time.sleep(random.uniform(MIN_DELAY_SECONDS, MAX_DELAY_SECONDS))

    def request(self, method: str, url: str, **kwargs) -> requests.Response | None:
        """GET/POST with retry on 429/5xx and on transport errors."""
        kwargs.setdefault("timeout", TIMEOUT)
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                resp = self.session.request(method, url, **kwargs)
                if resp.status_code in RETRY_STATUS:
                    log.warning(
                        "HTTP %s on %s (attempt %d/%d)", resp.status_code, url, attempt + 1, MAX_RETRIES
                    )
                    time.sleep(2**attempt + random.uniform(0.3, 1.2))
                    continue
                resp.raise_for_status()
                return resp
            except requests.exceptions.RequestException as exc:
                last_error = exc
                log.warning("Request failed for %s (attempt %d/%d): %s", url, attempt + 1, MAX_RETRIES, exc)
                time.sleep(2**attempt + random.uniform(0.3, 1.2))

        log.error("Giving up on %s: %s", url, last_error)
        return None

    def get_text(self, url: str, **kwargs) -> str:
        resp = self.request("GET", url, **kwargs)
        return resp.text if resp is not None else ""

    # -- contract -------------------------------------------------------------
    @abstractmethod
    def scrape(self, limit: int) -> list[CompetitionRecord]:
        """Return up to `limit` competition records for this source."""

    def _make_record(self, **kwargs) -> CompetitionRecord:
        kwargs.setdefault("id", f"{self.source_id}_{kwargs.get('event_id', '')}")
        kwargs.setdefault("source_id", self.source_id)
        return CompetitionRecord(**kwargs)
