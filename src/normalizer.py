"""Text normalization: Indonesian date parsing, URL canonicalization, link splitting."""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

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

# Patterns are tried in order; each returns (day, month, year|None).
_DATE_PATTERNS: list[tuple[str, str]] = [
    (r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", "ymd"),
    (r"\b(\d{1,2})\s+([a-z]+)\s+(?:tahun\s+)?(\d{4})\b", "dmy"),
    (r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", "dmy_num"),
    (r"\b(\d{1,2})-(\d{1,2})-(\d{4})\b", "dmy_num"),
    (r"\b(\d{1,2})\s+([a-z]+)\b", "dm"),
]

# "12 Sep - 26 Okt 2026" -> keep the right side of the range. Month names are
# required so that plain numeric dates ("10-10-2026") are never split.
_RANGE_RE = re.compile(r"(\d{1,2}\s+[a-zA-Z]+)\s*[-–—]+\s*(\d{1,2}\s+[a-zA-Z]+(?:\s+\d{4})?)")

_TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "_ga", "ref_src"}

REG_LINK_KEYWORDS = (
    "daftar", "registrasi", "register", "registration",
    "formulir", "pendaftaran", "gform", "linktr.ee",
    "typeform", "forms.gle", "tally.so", "报名",
)
GUIDE_LINK_KEYWORDS = (
    "panduan", "guide", "juklak", "juknis", "rulebook",
    "booklet", "pedoman", "syarat", "ketentuan", "silabus",
    "drive.google.com", "dropbox", ".pdf",
)
DEADLINE_CONTEXT_RE = re.compile(
    r"(?:deadline|batas\s+pendaftaran|periode\s+pendaftaran|pendaftaran\s+ditutup|"
    r"terakhir|sampai|ditutup|penutupan|last\s+day)\s*[:\-]?\s*"
    r"(\d{1,2}\s+[a-zA-Z]+\s+\d{4}|\d{1,2}[/-]\d{1,2}[/-]\d{4}|\d{4}-\d{1,2}-\d{1,2})",
    re.IGNORECASE,
)


def _month_number(token: str) -> int | None:
    t = token.lower()[:3]
    return ID_MONTHS.get(t) or ID_MONTHS.get(token.lower())


def _candidates(text: str) -> list[tuple[datetime, bool]]:
    """All date candidates found in text, flagged with has_year."""
    found: list[tuple[datetime, bool]] = []
    for pattern, kind in _DATE_PATTERNS:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            try:
                if kind == "ymd":
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if not 1 <= mo <= 12:
                        continue
                    found.append((datetime(y, mo, d), True))
                elif kind == "dmy":
                    d, mo, y = int(m.group(1)), _month_number(m.group(2)), int(m.group(3))
                    if not mo:
                        continue
                    found.append((datetime(y, mo, d), True))
                elif kind == "dmy_num":
                    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if not 1 <= mo <= 12:
                        continue
                    found.append((datetime(y, mo, d), True))
                else:  # "dm" -> no year
                    d, mo = int(m.group(1)), _month_number(m.group(2))
                    if not mo:
                        continue
                    found.append((datetime(2000, mo, d), False))
            except ValueError:
                continue
    return found


def parse_indonesian_date(date_str: str | None, year_hint: int | None = None) -> tuple[str | None, datetime | None]:
    """Parse an Indonesian/ISO date string.

    Handles ranges ("12 Sep - 26 Okt 2026" -> closing boundary), ISO, DD/MM/YYYY,
    DD-MM-YYYY and bare "DD Month". `year_hint` resolves bare dates to that year
    instead of the next upcoming one -- article sources know the event year.
    Returns (YYYY-MM-DD or None, datetime or None).
    """
    if not date_str:
        return None, None

    clean = str(date_str).lower().strip()
    if not clean:
        return None, None

    # If a range is present, only the closing side is the deadline.
    rng = _RANGE_RE.search(clean)
    if rng:
        right = rng.group(2).strip()
        year = re.search(r"\b(20\d{2})\b", clean)
        if year and not re.search(r"\b20\d{2}\b", right):
            right = f"{right} {year.group(1)}"
        clean = right

    candidates = _candidates(clean)
    if not candidates:
        return None, None

    with_year = [c for c in candidates if c[1]]
    if with_year:
        best = max(with_year, key=lambda c: c[0])
        return best[0].strftime("%Y-%m-%d"), best[0]

    # No explicit year: use the hint when the caller knows the event year.
    if year_hint:
        best_dt = None
        for dt, _ in candidates:
            try:
                cand = dt.replace(year=year_hint)
            except ValueError:
                continue
            if best_dt is None or cand > best_dt:
                best_dt = cand
        if best_dt:
            return best_dt.strftime("%Y-%m-%d"), best_dt

    # No explicit year: pick the nearest upcoming occurrence of each candidate.
    now = datetime.now()
    best_dt, best_gap = None, None
    for dt, _ in candidates:
        for year in (now.year, now.year + 1):
            try:
                cand = dt.replace(year=year)
            except ValueError:
                continue
            gap = (cand - now).days
            if gap < -1:
                continue
            if best_gap is None or gap < best_gap:
                best_dt, best_gap = cand, gap
    if best_dt is None:
        best_dt = max(dt for dt, _ in candidates)
    return best_dt.strftime("%Y-%m-%d"), best_dt


def is_expired(deadline: str | None, grace_days: int = 0) -> bool:
    """True when the deadline day is already past (unknown deadline = not expired).

    Compared on dates, not timestamps: a competition closing *today* is still open.
    """
    if not deadline:
        return False
    try:
        dt = datetime.strptime(deadline[:10], "%Y-%m-%d").date()
    except ValueError:
        return False
    return dt < (datetime.now().date() - timedelta(days=grace_days))


def normalize_url(url: str | None) -> str:
    """Canonicalize a URL: lowercase host, strip tracking params + fragment.

    Keeps meaningful query strings (unlike the previous version, which dropped
    them entirely and merged distinct listings).
    """
    if not url:
        return "-"
    raw = str(url).strip()
    if not raw.startswith("http"):
        return "-"
    try:
        p = urlparse(raw)
        query = [
            (k, v)
            for k, v in parse_qsl(p.query, keep_blank_values=True)
            if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
        ]
        path = p.path.rstrip("/") or "/"
        return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(query), ""))
    except Exception:
        return raw


def html_to_text(html: str | None) -> str:
    """Flatten an HTML fragment to plain text.

    NFKC is applied so that the "math bold" letters Blogger/Instagram posts use
    ("𝟏𝟒 𝐉𝐮𝐧𝐢 𝟐𝟐𝟐𝟔") become plain "14 Juni 2026" and stay parseable.
    """
    if not html:
        return ""
    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", str(html))
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text)).strip()


_IMAGE_EXT_RE = re.compile(r"\.(png|jpe?g|gif|webp|svg|bmp)(\?|$)", re.IGNORECASE)
_SOCIAL_HOSTS = (
    "facebook.com", "fb.com", "instagram.com", "twitter.com", "x.com",
    "youtube.com", "youtu.be", "linkedin.com", "tiktok.com", "pinterest.",
    "threads.net", "reddit.com",
)


def _is_usable_link(url: str) -> bool:
    """False for images, social profiles and non-http targets."""
    if not url or not url.lower().startswith("http"):
        return False
    if _IMAGE_EXT_RE.search(url):
        return False
    if any(host in url.lower() for host in _SOCIAL_HOSTS):
        return False
    return True


def split_links(
    links: list[dict[str, str]], own_domain: str
) -> tuple[str, str]:
    """Split external links into (registration_url, guidebook_url).

    Posters/images and social profiles are ignored -- they are never a
    registration target. The registration column falls back to the first
    remaining external link; the guidebook column stays "-" unless a guide-ish
    link is actually present.
    """
    external = [
        lk for lk in links
        if lk["url"].startswith("http") and own_domain not in lk["url"] and _is_usable_link(lk["url"])
    ]
    reg, guide = "-", "-"

    # Guides win first: a "GuideBook" short link must not swallow the registration slot.
    for lk in external:
        text, url = lk["text"].lower(), lk["url"].lower()
        if guide == "-" and any(k in text or k in url for k in GUIDE_LINK_KEYWORDS):
            guide = lk["url"]

    for lk in external:
        text, url = lk["text"].lower(), lk["url"].lower()
        if lk["url"] == guide:
            continue
        if reg == "-" and any(k in text or k in url for k in REG_LINK_KEYWORDS):
            reg = lk["url"]

    leftovers = [lk["url"] for lk in external if lk["url"] not in (reg, guide)]
    if reg == "-" and leftovers:
        reg = leftovers.pop(0)
    return reg, guide


def extract_deadline_from_text(text: str | None, year_hint: int | None = None) -> str | None:
    """Pull a deadline mentioned in free-form prose."""
    if not text:
        return None
    m = DEADLINE_CONTEXT_RE.search(text)
    if not m:
        return None
    parsed, _ = parse_indonesian_date(m.group(1), year_hint)
    return parsed


_REG_PHASE_RE = re.compile(
    r"(?:early\s+bird\s+)?(?:registration|pendaftaran|registrasi)\b", re.IGNORECASE
)


def guess_registration_deadline(text: str | None, year_hint: int | None = None) -> str | None:
    """Closing date of the latest registration phase mentioned in the prose.

    Pages that publish a timeline ("Batch 1 Registration 24 Jul - 30 Aug 2026,
    Batch 2 Registration 31 Aug - 2 Oct 2026") carry no explicit "deadline"
    label, so the newest registration window is used instead.
    """
    if not text:
        return None
    best: datetime | None = None
    for m in _REG_PHASE_RE.finditer(text):
        window = text[m.end(): m.end() + 70]
        if re.match(r"\s*\w{0,12}\s*(?:ulang|semifinalis|babak|final)", window, re.IGNORECASE):
            continue
        parsed, dt = parse_indonesian_date(window, year_hint)
        if dt and (best is None or dt > best):
            best = dt
    return best.strftime("%Y-%m-%d") if best else None


# --- cheap heuristics used when the LLM fallback is unavailable --------------
_RP_RE = re.compile(r"Rp\.?\s?[\d.,]{3,}")
_FREE_RE = re.compile(r"\b(gratis|free|tanpa\s+biaya|0\s*idr)\b", re.IGNORECASE)


def guess_fee(text: str | None) -> str:
    """Best-effort fee string from free-form text."""
    if not text:
        return "-"
    if _FREE_RE.search(text):
        return "GRATIS"
    m = _RP_RE.search(text)
    return m.group(0).strip() if m else "-"


def guess_location(text: str | None) -> str:
    """Online / Offline / Hybrid from free-form text."""
    if not text:
        return "-"
    t = text.lower()
    online = "online" in t or "daring" in t or "zoom" in t or "google meet" in t
    offline = bool(re.search(r"offline|tatap\s*muka|on[- ]site|di lokasi| onsite", t))
    if online and offline:
        return "Hybrid"
    if online:
        return "Online"
    if offline:
        return "Offline"
    return "-"


_TARGET_PATTERNS = [
    ("Mahasiswa", r"\bmahasiswa\b|\bs1\b|\bs2\b|\bs3\b|perguruan tinggi|universitas"),
    ("SMA / Sederajat", r"\bsma\b|\bsmk\b|sederajat|kelas 12"),
    ("SMP / Sederajat", r"\bsmp\b|sederajat"),
    ("SD / Sederajat", r"\bsd\b|\bsd\b|kelas 6"),
    ("Umum", r"\bumum\b|terbuka untuk semua|general public"),
]


def guess_target(text: str | None) -> str:
    """Target audience string from free-form text."""
    if not text:
        return "-"
    hits = [label for label, pattern in _TARGET_PATTERNS if re.search(pattern, text, re.IGNORECASE)]
    return ", ".join(hits) if hits else "-"


_ORG_RE = re.compile(
    r"\b(?:universitas|univ\w*|institute|institut|akademi|politeknik|sekolah|hospital|"
    r"hima|him\w*|bem|dema|ukm|fkm|feb|fisip|fikom|ftik|fsa|pmi|lpm|komite|panitia|"
    r"foundation|yayasan|company|pt|corporation|inc|group|organisasi|komunitas)\b",
    re.IGNORECASE,
)


_ORG_STOPWORDS = {
    "harus", "dari", "dengan", "untuk", "yang", "serta", "agar", "sehingga",
    "dan", "atau", "ini", "tersebut", "adalah", "bisa", "dapat", "akan",
    "sudah", "telah", "pada", "dalam", "juga", "lebih", "paling", "banyak",
    "the", "and", "with", "from", "this", "that",
}


def guess_organizer(text: str | None, title: str | None = None) -> str:
    """Institution name: the first line that looks like an organisation."""
    if not text:
        return "-"
    for line in re.split(r"[.\n\r|]", text):
        line = line.strip(" -•\t")
        if not (3 < len(line) < 80):
            continue
        if "/" in line or "http" in line.lower():
            continue
        words = line.split()
        if len(words) < 2 or len(words) > 8:
            continue
        if any(w.strip(".,:()").lower() in _ORG_STOPWORDS for w in words):
            continue
        if title and line.lower().startswith(title.lower()[:25]):
            continue
        if _ORG_RE.search(line):
            return line
    return "-"
