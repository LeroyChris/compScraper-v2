"""Google Sheets writer with anti-leak deduplication.

The sheet is the source of truth: every tab is scanned for previously seen
URLs / titles / deadlines before new rows are appended, so nothing is ever
written twice and nothing is ever deleted (rejected rows stay in `Arsip Reject`).
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from src.config import (
    GOOGLE_SERVICE_ACCOUNT_FILE,
    SHEET_AUDIT_TAB,
    SPREADSHEET_ID,
)
from src.models import (
    COL_DEADLINE,
    COL_SOURCE_URL,
    COL_TITLE,
    HEADERS,
    CompetitionRecord,
)
from src.normalizer import normalize_url

log = logging.getLogger("compScraper-v2")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsSync:
    def __init__(self, sheet_id: str | None = None, creds: str | None = None, audit_tab: str | None = None):
        self.sheet_id = sheet_id or SPREADSHEET_ID
        self.audit_tab = audit_tab or SHEET_AUDIT_TAB
        self.creds_source = (
            creds
            or os.getenv("GSPREAD_SERVICE_ACCOUNT_JSON")
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
            or GOOGLE_SERVICE_ACCOUNT_FILE
        )
        if not Path(self.creds_source).exists() and not self.creds_source.strip().startswith("{"):
            self.creds_source = ""

        self.client = None
        self.doc = None
        self.audit_sheet = None
        self.seen_urls: set[str] = set()
        self.seen_entries: list[tuple[str, str | None]] = []

        self._init_client()
        if self.doc:
            self.audit_sheet = self._ensure_audit_sheet()
            self._load_anti_leak_snapshot()

    # -- connection -----------------------------------------------------------
    def _init_client(self) -> None:
        if not self.sheet_id or not self.creds_source:
            log.error("SHEET_ID / credentials missing. Sheets integration disabled.")
            return
        try:
            import gspread
            from google.oauth2.service_account import Credentials

            if self.creds_source.strip().startswith("{"):
                creds = Credentials.from_service_account_info(
                    json.loads(self.creds_source), scopes=SCOPES
                )
            else:
                creds = Credentials.from_service_account_file(self.creds_source, scopes=SCOPES)

            self.client = gspread.authorize(creds)
            self.doc = self.client.open_by_key(self.sheet_id)
            log.info("Connected to spreadsheet: %s", self.doc.title)
        except Exception as exc:
            log.error("Failed to connect to Google Sheets: %s", exc, exc_info=True)

    def _ensure_audit_sheet(self):
        ws = None
        for name in {self.audit_tab, "Tab Audit", "DRAFT"}:
            try:
                ws = self.doc.worksheet(name)
                break
            except Exception:
                continue

        if ws is None:
            ws = self.doc.add_worksheet(title=self.audit_tab, rows=1000, cols=len(HEADERS))
            ws.append_row(HEADERS, value_input_option="RAW")
            log.info("Created worksheet '%s' with %d headers.", self.audit_tab, len(HEADERS))
            return ws

        rows = ws.get_all_values()
        if not rows:
            ws.append_row(HEADERS, value_input_option="RAW")
        elif rows[0] != HEADERS:
            log.warning(
                "Header mismatch in '%s' (expected %d cols, found %d). Repairing to canonical schema.",
                ws.title, len(HEADERS), len(rows[0]),
            )
            ws.update([HEADERS], "A1")
        return ws

    # -- anti-leak ------------------------------------------------------------
    def _load_anti_leak_snapshot(self) -> None:
        """Scan every tab: URL Sumber (12), Judul Lomba (1), Deadline (6)."""
        for ws in self.doc.worksheets():
            try:
                records = ws.get_all_values()
            except Exception as exc:
                log.warning("Snapshot read failed for tab '%s': %s", ws.title, exc)
                continue

            for row in records[1:]:
                if len(row) > COL_SOURCE_URL:
                    norm = normalize_url(row[COL_SOURCE_URL])
                    if norm != "-":
                        self.seen_urls.add(norm)
                title = row[COL_TITLE] if len(row) > COL_TITLE else ""
                deadline = row[COL_DEADLINE] if len(row) > COL_DEADLINE else None
                if deadline in ("-", ""):
                    deadline = None
                if title:
                    self.seen_entries.append((title, deadline))

            if records:
                log.info(
                    "Anti-leak snapshot: tab '%s' scanned (%d urls, %d titles cached)",
                    ws.title, len(self.seen_urls), len(self.seen_entries),
                )

    # -- writing --------------------------------------------------------------
    def append_items(self, items: list[CompetitionRecord]) -> int:
        if not items or not self.audit_sheet:
            return 0
        rows = [it.to_row() for it in items]
        self.audit_sheet.append_rows(rows, value_input_option="RAW")
        log.info("Appended %d rows to '%s'.", len(rows), self.audit_sheet.title)
        return len(rows)

    def write_local_copy(self, items: list[CompetitionRecord]) -> Path:
        """Mirror the pushed rows to data/ for debugging (not a source of truth)."""
        out = Path(__file__).resolve().parent.parent / "data" / "latest_scraped_output.json"
        payload: list[dict[str, Any]] = [it.to_dict() for it in items]
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return out
