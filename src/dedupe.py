"""Cross-source deduplication.

The spreadsheet is the store of truth, so dedup compares against the sheet
snapshot (URL / title / deadline) plus records collected in the current run.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime

from src.models import CompetitionRecord

log = logging.getLogger("compScraper-v2")

STOPWORDS = {
    "lomba", "kompetisi", "competition", "fest", "festival", "nasional", "national",
    "international", "internasional", "tahun", "tingkat", "mahasiswa", "event", "fair",
    "2024", "2025", "2026", "2027", "ke", "dan", "di", "the", "of", "and", "se", "indonesia",
    "open", "call", "paper", "program", "2028", "2029", "seminar", "workshop",
    # prize decorations: the same competition is advertised with and without them
    "hadiah", "gratis", "juta", "jutaan", "jt", "ribu", "rp", "idr", "bonus",
}

JACCARD_THRESHOLD = 0.70
DEADLINE_PROXIMITY_DAYS = 4


def normalize_title_tokens(title: str) -> set[str]:
    clean = re.sub(r"[^a-zA-Z0-9\s]", " ", (title or "").lower())
    return {t for t in clean.split() if len(t) > 2 and t not in STOPWORDS}


def compute_fingerprint(title: str, deadline: str | None) -> str:
    tokens = sorted(normalize_title_tokens(title))
    payload = f"{'_'.join(tokens)}|{deadline or 'nodate'}"
    return hashlib.md5(payload.encode("utf-8")).hexdigest()[:16]


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def deadlines_proximate(d1: str | None, d2: str | None, max_days: int = DEADLINE_PROXIMITY_DAYS) -> bool:
    if not d1 or not d2:
        return True
    try:
        dt1 = datetime.strptime(d1[:10], "%Y-%m-%d")
        dt2 = datetime.strptime(d2[:10], "%Y-%m-%d")
    except ValueError:
        return True
    return abs((dt1 - dt2).days) <= max_days


class Deduplicator:
    """Filters candidates against the sheet snapshot and against this run."""

    def __init__(self, known_urls: set[str] | None = None, known_entries: list[tuple[str, str | None]] | None = None):
        self.known_urls = set(known_urls or ())
        self.known_entries = list(known_entries or ())  # (title, deadline)
        self.seen: list[CompetitionRecord] = []

    def _matches_known(self, record: CompetitionRecord) -> str:
        if record.source_url != "-" and record.source_url in self.known_urls:
            return f"URL already in sheet: {record.source_url}"

        tokens = normalize_title_tokens(record.title)
        for title, deadline in self.known_entries:
            similarity = jaccard(tokens, normalize_title_tokens(title))
            if similarity >= JACCARD_THRESHOLD and deadlines_proximate(record.deadline, deadline):
                return f"fuzzy title match {similarity:.2f} with '{title[:50]}'"
        return ""

    def is_duplicate(self, record: CompetitionRecord) -> tuple[bool, str]:
        reason = self._matches_known(record)
        if reason:
            return True, reason

        for other in self.seen:
            if other.source_url != "-" and other.source_url == record.source_url:
                return True, f"duplicate URL in this run: {record.source_url}"
            similarity = jaccard(
                normalize_title_tokens(record.title), normalize_title_tokens(other.title)
            )
            if similarity >= JACCARD_THRESHOLD and deadlines_proximate(record.deadline, other.deadline):
                return True, f"fuzzy title match {similarity:.2f} with '{other.title[:50]}'"
        return False, ""

    def filter_new(self, records: list[CompetitionRecord]) -> list[CompetitionRecord]:
        fresh: list[CompetitionRecord] = []
        for record in records:
            dup, reason = self.is_duplicate(record)
            if dup:
                log.info("Dedup drop [%s]: %s", record.id, reason)
                continue
            fresh.append(record)
            self.seen.append(record)
        return fresh
