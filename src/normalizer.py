"""Text normalization and Indonesian date parsing utilities."""

from __future__ import annotations

import re
from datetime import datetime

ID_MONTHS = {
    "jan": 1, "januari": 1,
    "feb": 2, "februari": 2,
    "mar": 3, "maret": 3,
    "apr": 4, "april": 4,
    "mei": 5, "may": 5,
    "jun": 6, "juni": 6,
    "jul": 7, "juli": 7,
    "agu": 8, "agustus": 8, "agt": 8,
    "sep": 9, "september": 9,
    "okt": 10, "oktober": 10,
    "nov": 11, "november": 11,
    "des": 12, "desember": 12,
}


def parse_indonesian_date(date_str: str | None) -> tuple[str, datetime | None]:
    """Parse Indonesian date string.

    Returns:
        tuple (formatted_date_str "YYYY-MM-DD" or "-", datetime_object or None)
    """
    if not date_str:
        return "-", None

    clean = date_str.lower().strip()
    if "-" in clean and not re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
        # Range given (e.g. "12 Sep - 26 Okt 2026"), take closing boundary
        clean = clean.split("-")[-1].strip()

    # Pattern 1: ISO YYYY-MM-DD
    iso_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", clean)
    if iso_match:
        y, m, d = iso_match.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d"), dt
        except ValueError:
            return "-", None

    # Pattern 2: DD Month YYYY (e.g. 26 Oktober 2026)
    match_with_year = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", clean)
    if match_with_year:
        d, m_name, y = match_with_year.groups()
        m_val = ID_MONTHS.get(m_name[:3]) or ID_MONTHS.get(m_name)
        if m_val:
            try:
                dt = datetime(int(y), m_val, int(d))
                return dt.strftime("%Y-%m-%d"), dt
            except ValueError:
                return "-", None

    # Pattern 3: DD/MM/YYYY or DD-MM-YYYY
    slash_match = re.search(r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", clean)
    if slash_match:
        d, m, y = slash_match.groups()
        try:
            dt = datetime(int(y), int(m), int(d))
            return dt.strftime("%Y-%m-%d"), dt
        except ValueError:
            return "-", None

    # Pattern 4: DD Month without year (assume current or next year)
    match_no_year = re.search(r"(\d{1,2})\s+([a-z]+)", clean)
    if match_no_year:
        d, m_name = match_no_year.groups()
        m_val = ID_MONTHS.get(m_name[:3]) or ID_MONTHS.get(m_name)
        if m_val:
            now = datetime.now()
            year = now.year if m_val >= now.month - 1 else now.year + 1
            try:
                dt = datetime(year, m_val, int(d))
                return dt.strftime("%Y-%m-%d"), dt
            except ValueError:
                return "-", None

    return "-", None
