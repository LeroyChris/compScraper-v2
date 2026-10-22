"""Canonical record model + sheet schema.

One record == one row in the audit sheet. Header order is the contract with
the spreadsheet and with scripts/Code.gs (column indices are referenced by
name there, but the order is kept identical to the legacy `Tab Audit` tab so
existing rows stay readable).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

HEADERS = [
    "ID",
    "Judul Lomba",
    "Penyelenggara",
    "Lokasi",
    "Sasaran",
    "Biaya",
    "Deadline",
    "Rekomendasi School",
    "Confidence",
    "Status Review",
    "Link Pendaftaran",
    "Link Panduan",
    "URL Sumber",
    "Deskripsi Singkat",
    "Tanggal Scrape",
]

# Column indices used by the anti-leak snapshot (kept in sync with HEADERS).
COL_ID = 0
COL_TITLE = 1
COL_DEADLINE = 6
COL_REG_URL = 10
COL_SOURCE_URL = 12

# Emoji / dingbat blocks only. Ranges deliberately exclude CJK (U+4E00..U+9FFF)
# and other legitimate scripts -- an earlier version swallowed them.
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0000FE0F\U0000200D\U000020E3]"
)
_INVISIBLE_RE = re.compile("[\u200b-\u200f\ufeff\u2060]")


def sanitize_text(text: str | None, fallback: str = "-") -> str:
    """Normalize text: NFKC, strip emoji/invisibles, collapse whitespace."""
    if text is None:
        return fallback
    clean = unicodedata.normalize("NFKC", str(text))
    clean = _EMOJI_RE.sub("", clean)
    clean = _INVISIBLE_RE.sub("", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean if clean else fallback


class TriageStatus(str, Enum):
    """Audit triage states. Names are read by scripts/Code.gs (AUTO_APPROVE)."""

    AUTO_APPROVE = "AUTO_APPROVE"
    PERLU_REVIEW = "PERLU_REVIEW"
    MANUAL_CHECK = "MANUAL_CHECK"


class CompetitionRecord(BaseModel):
    """A single competition listing."""

    id: str
    source_id: str
    title: str
    organizer: str = "-"
    location: str = "-"
    target: str = "-"
    fee: str = "-"
    deadline: str | None = None
    registration_url: str = "-"
    guidebook_url: str = "-"
    source_url: str = "-"
    description: str = ""
    school: str = "UMUM"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status_review: TriageStatus = TriageStatus.MANUAL_CHECK
    scraped_at: str = ""

    @field_validator("title", "organizer", "location", "target", "fee", mode="before")
    @classmethod
    def _clean(cls, v: Any) -> str:
        return sanitize_text(v, "-")

    @field_validator("description", mode="before")
    @classmethod
    def _clean_desc(cls, v: Any) -> str:
        return sanitize_text(v, "")

    @field_validator("deadline", mode="before")
    @classmethod
    def _clean_deadline(cls, v: Any) -> str | None:
        if v in (None, "", "-", "TBD"):
            return None
        s = str(v).strip()
        try:
            return datetime.strptime(s[:10], "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            return None

    @field_validator("registration_url", "guidebook_url", "source_url", mode="before")
    @classmethod
    def _clean_url(cls, v: Any) -> str:
        s = str(v or "-").strip()
        return s if s.startswith("http") else "-"

    @property
    def short_description(self) -> str:
        """One-line summary used as the IG caption draft."""
        return self.description[:200]

    def to_row(self) -> list[str]:
        return [
            self.id,
            self.title,
            self.organizer,
            self.location,
            self.target,
            self.fee,
            self.deadline or "-",
            self.school,
            f"{self.confidence:.2f}",
            self.status_review.value,
            self.registration_url,
            self.guidebook_url,
            self.source_url,
            self.short_description,
            self.scraped_at,
        ]

    def to_dict(self) -> dict[str, Any]:
        return dict(zip(HEADERS, self.to_row()))
