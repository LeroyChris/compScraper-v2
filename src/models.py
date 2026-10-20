"""Data models and text sanitization helpers for compScraper-v2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse, urlunparse

HEADERS = [
    "Scraped At",
    "Judul Lomba",
    "Penyelenggara",
    "Rekomendasi School",
    "Biaya Pendaftaran",
    "Deadline",
    "Link Sumber",
    "Link Pendaftaran",
    "Link Guidebook",
    "Status Review",
]


def sanitize_text(text: str | None, fallback: str = "-") -> str:
    """Trim, remove control characters and collapse multiple whitespaces."""
    if not text:
        return fallback
    clean = re.sub(r"\s+", " ", text).strip()
    return clean if clean else fallback


def normalize_url(url: str | None) -> str:
    """Normalize URL by stripping tracking parameters, trailing slash, and lowercase netloc."""
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


@dataclass
class CompetitionItem:
    scraped_at: str
    title: str
    organizer: str
    school: str
    fee: str
    deadline: str
    source_url: str
    registration_url: str
    guidebook_url: str
    status_review: str = "Pending"

    def to_row(self) -> list[str]:
        return [
            self.scraped_at,
            self.title,
            self.organizer,
            self.school,
            self.fee,
            self.deadline,
            self.source_url,
            self.registration_url,
            self.guidebook_url,
            self.status_review,
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "Scraped At": self.scraped_at,
            "Judul Lomba": self.title,
            "Penyelenggara": self.organizer,
            "Rekomendasi School": self.school,
            "Biaya Pendaftaran": self.fee,
            "Deadline": self.deadline,
            "Link Sumber": self.source_url,
            "Link Pendaftaran": self.registration_url,
            "Link Guidebook": self.guidebook_url,
            "Status Review": self.status_review,
        }
