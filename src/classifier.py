"""Rule-based 6-School keyword classifier for Cakrawala University."""

from __future__ import annotations

import logging
import re

log = logging.getLogger("compScraper-v2")

PRIORITY = ["SLA", "SPE", "SCD", "SBE", "SEN", "UMUM"]

KEYWORDS: dict[str, list[str]] = {
    "SLA": ["moot court", "hukum", "debat hukum", "esai hukum", "legal", "perdata", "pidana"],
    "SPE": ["psikologi", "pendidikan", "guru", "kesehatan mental", "teaching", "edukasi", "paud", "konseling"],
    "SCD": [
        "desain grafis", "poster", "film", "fotografi", "jurnalistik",
        "komunikasi", "ui/ux", "videografi", "animasi", "broadcast", "branding", "iklan"
    ],
    "SBE": [
        "business plan", "bisnis", "entrepreneur", "investasi", "akuntansi",
        "manajemen", "case competition", "marketing", "keuangan", "finansial", "ekonomi"
    ],
    "SEN": [
        "programming", "coding", "machine learning", "artificial intelligence",
        "robotik", "iot", "hackathon", "data science", "elektronika",
        "software", "web development", "cyber security", "informatika", "teknik"
    ],
    "UMUM": ["keagamaan", "mtq", "olahraga", "e-sports", "esai", "puisi", "karya tulis", "debat"]
}


def classify_school(title: str, description: str) -> tuple[str, list[str]]:
    """Determine primary School based on keyword weights with priority tie-break.

    Title match: weight 2
    Description match: weight 1

    Returns:
        tuple (primary_school: str, secondary_schools: list[str])
    """
    title_l = title.lower()
    desc_l = description.lower()
    scores: dict[str, int] = {}

    for school, words in KEYWORDS.items():
        score = 0
        for w in words:
            pattern = rf"\b{re.escape(w)}\b"
            if re.search(pattern, title_l):
                score += 2
            elif re.search(pattern, desc_l):
                score += 1
        scores[school] = score

    matched = [(school, score) for school, score in scores.items() if score > 0]
    if not matched:
        return "UMUM", []

    # Sort by score descending, then tie-break using PRIORITY rank
    matched.sort(key=lambda x: (x[1], -PRIORITY.index(x[0])), reverse=True)
    primary = matched[0][0]
    secondaries = [s for s, _ in matched[1:] if s != "UMUM"]
    return primary, secondaries
