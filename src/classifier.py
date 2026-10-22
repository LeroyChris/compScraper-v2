"""Two-layer classifier: noise filter + weighted school matching.

Layer 1 drops non-competition content (job ads, scholarships, webinars, ...).
Layer 2 scores the six Cakrawala schools and derives a confidence score that
drives the audit triage (blacklist = MANUAL_CHECK).
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from src.config import KEYWORDS_FILE
from src.models import CompetitionRecord, TriageStatus

log = logging.getLogger("compScraper-v2")

AUTO_APPROVE_AT = 0.85
PERLU_REVIEW_AT = 0.50
CONFIDENCE_CEILING = 90.0  # score that maps to confidence 1.0

# "9+ Cara Lomba Agar Bisa Menjadi Juara" -- listicles, not competitions.
# Anchored to the title: real competition articles use the same words in the body.
TITLE_NOISE_RE = re.compile(
    r"^\s*(\d+\s*\+\s*(cara|tips|ide|alasan|manfaat|langkah)|"
    r"tips\s*(&|dan)\s*trick|trik\s*(&|dan)\s*tips|cara menjadi juara|"
    r"cara\s*(&|dan)\s*syarat)",
    re.IGNORECASE,
)
# A title that names a competition wins over a noisy body ("... Seminar Festival ...").
COMPETITION_TITLE_RE = re.compile(
    r"\b(lomba|kompetisi|competition|festival|fest|contest|olimpiade|olympiad)\b",
    re.IGNORECASE,
)


class CompetitionClassifier:
    def __init__(self, keywords_file: Path = KEYWORDS_FILE):
        with open(keywords_file, encoding="utf-8") as f:
            data = json.load(f)

        self.noise_patterns = [
            re.compile(p, re.IGNORECASE) for p in data.get("noise_patterns", [])
        ]

        self.schools: dict[str, list[tuple[re.Pattern, int]]] = {}
        for school, spec in data.get("schools", {}).items():
            compiled = []
            for keyword, weight in spec.get("keywords", {}).items():
                compiled.append((re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE), weight))
            self.schools[school] = compiled

    # -- layer 1 --------------------------------------------------------------
    def is_noise(self, text: str) -> bool:
        return any(p.search(text) for p in self.noise_patterns)

    # -- layer 2 --------------------------------------------------------------
    def classify(self, title: str, description: str, has_deadline: bool, has_reg_url: bool) -> dict[str, Any]:
        title_l, desc_l = title.lower(), description.lower()
        looks_like_competition = bool(COMPETITION_TITLE_RE.search(title_l))
        noise = (
            TITLE_NOISE_RE.match(title_l)
            or self.is_noise(title_l)
            or (not looks_like_competition and self.is_noise(desc_l))
        )
        if noise:
            return {
                "is_competition": False,
                "school": "UMUM",
                "confidence": 0.0,
                "scores": {},
                "status_review": TriageStatus.MANUAL_CHECK,
            }

        scores: dict[str, int] = {}
        for school, patterns in self.schools.items():
            total = 0
            for pattern, weight in patterns:
                if pattern.search(title_l):
                    total += weight * 2
                elif pattern.search(desc_l):
                    total += weight
            if total > 0:
                scores[school] = total

        if not scores:
            return {
                "is_competition": True,
                "school": "UMUM",
                "confidence": 0.30,
                "scores": {},
                "status_review": TriageStatus.MANUAL_CHECK,
            }

        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        school, top_score = ranked[0]
        confidence = min(top_score / CONFIDENCE_CEILING, 0.98)

        # Completeness bonus: a record with a deadline and a registration link is
        # far more likely to be a real, postable competition.
        if has_deadline:
            confidence += 0.03
        if has_reg_url:
            confidence += 0.03
        confidence = round(min(confidence, 0.98), 2)

        if confidence >= AUTO_APPROVE_AT:
            status = TriageStatus.AUTO_APPROVE
        elif confidence >= PERLU_REVIEW_AT:
            status = TriageStatus.PERLU_REVIEW
        else:
            status = TriageStatus.MANUAL_CHECK

        return {
            "is_competition": True,
            "school": school,
            "confidence": confidence,
            "scores": dict(ranked),
            "status_review": status,
        }

    def enrich(self, record: CompetitionRecord) -> CompetitionRecord | None:
        """Fill school/confidence/status on a record. Returns None if it is noise."""
        result = self.classify(
            record.title,
            record.description,
            bool(record.deadline),
            record.registration_url != "-",
        )
        if not result["is_competition"]:
            log.info("Noise drop [%s]: %s", record.id, record.title[:60])
            return None

        record.school = result["school"]
        record.confidence = result["confidence"]
        record.status_review = result["status_review"]
        return record
