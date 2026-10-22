"""Central configuration. Loaded from environment / .env."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")

DATA_DIR = ROOT_DIR / "data"
LOGS_DIR = ROOT_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# --- Google Sheets -----------------------------------------------------------
SPREADSHEET_ID = os.getenv("SHEET_ID") or os.getenv("SPREADSHEET_ID", "")
SHEET_AUDIT_TAB = os.getenv("SHEET_AUDIT_TAB", "Tab Audit")
SHEET_MASTER_TAB = os.getenv("SHEET_MASTER_TAB", "Master Data Lomba")
SHEET_REJECT_TAB = os.getenv("SHEET_REJECT_TAB", "Arsip Reject")
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")

# --- Scraping ----------------------------------------------------------------
MAX_ITEMS_PER_RUN = int(os.getenv("MAX_ITEMS_PER_RUN", "40"))
MAX_PAGES = int(os.getenv("MAX_PAGES", "3"))
MIN_DELAY_SECONDS = float(os.getenv("MIN_DELAY_SECONDS", "2.0"))
MAX_DELAY_SECONDS = float(os.getenv("MAX_DELAY_SECONDS", "4.0"))
TIMEOUT = int(os.getenv("TIMEOUT", "20"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
# Grace period sebelum event dianggap kedaluwarsa (hari).
DEADLINE_GRACE_DAYS = int(os.getenv("DEADLINE_GRACE_DAYS", "0"))
# Artikel bebas-yang-tanpa-deadline: drop bila tanggal terakhir yang disebut
# sudah lewat lebih dari N hari (event-nya selesai).
STALE_ARTICLE_DAYS = int(os.getenv("STALE_ARTICLE_DAYS", "30"))

# --- AI (opsional) -----------------------------------------------------------
GEMINI_API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_AI_API_KEY")
    or os.getenv("GOOGLE_API_KEY", "")
)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")

KEYWORDS_FILE = DATA_DIR / "keywords.json"
