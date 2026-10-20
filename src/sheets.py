"""Google Sheets integration with Anti-Leak Deduplication across DRAFT & ARCHIVE tabs."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from src.models import HEADERS, CompetitionItem, normalize_url

log = logging.getLogger("compScraper-v2")


class SheetsSync:
    """Manages Anti-Leak Deduplication and RAW Batch Appending to Google Sheets."""

    def __init__(self, sheet_id: str | None = None, creds_path_or_json: str | None = None):
        self.sheet_id = sheet_id or os.getenv("SHEET_ID")
        self.creds_source = (
            creds_path_or_json
            or os.getenv("GSPREAD_SERVICE_ACCOUNT_JSON")
            or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        )
        if not self.creds_source and os.path.exists("credentials.json"):
            self.creds_source = "credentials.json"

        self.client = None
        self.doc = None
        self.draft_sheet = None
        self.seen_urls: set[str] = set()
        self.seen_titles: set[str] = set()

        self._init_client()
        if self.doc:
            self.draft_sheet = self._ensure_draft_sheet()
            self._load_anti_leak_snapshot()

    def _init_client(self):
        """Authorize gspread client via file or environment JSON string."""
        if not self.sheet_id or not self.creds_source:
            log.warning("Sheet ID or credentials missing. Running without live Sheets connection.")
            return

        try:
            import gspread
            from google.oauth2.service_account import Credentials

            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]

            if self.creds_source.strip().startswith("{"):
                info = json.loads(self.creds_source)
                creds = Credentials.from_service_account_info(info, scopes=scopes)
            elif Path(self.creds_source).exists():
                creds = Credentials.from_service_account_file(self.creds_source, scopes=scopes)
            else:
                log.error("Invalid credentials source provided.")
                return

            self.client = gspread.authorize(creds)
            self.doc = self.client.open_by_key(self.sheet_id)
            log.info("Connected to Google Spreadsheet: %s", self.doc.title)
        except Exception as e:
            log.error("Failed to connect to Google Sheets: %s", e, exc_info=True)

    def _ensure_draft_sheet(self):
        """Ensure tab DRAFT exists and has proper headers."""
        ws = None
        for name in ("DRAFT", "Draft"):
            try:
                ws = self.doc.worksheet(name)
                break
            except Exception:
                continue

        if not ws:
            ws = self.doc.add_worksheet(title="DRAFT", rows=1000, cols=len(HEADERS))
            ws.append_row(HEADERS, value_input_option="RAW")
            log.info("Created new worksheet 'DRAFT' with standard 10 headers.")
            return ws

        rows = ws.get_all_values()
        if not rows:
            ws.append_row(HEADERS, value_input_option="RAW")
        elif rows[0] != HEADERS:
            log.warning("Header mismatch in DRAFT sheet. Expected %d columns, found %d", len(HEADERS), len(rows[0]))
        return ws

    def _load_anti_leak_snapshot(self):
        """Anti-Leak: Ingest all URLs & Titles across DRAFT and ARCHIVE (Pending, Approved, Rejected)."""
        tabs_to_scan = ["DRAFT", "Draft", "ARCHIVE", "Archive"]
        for tab_name in tabs_to_scan:
            try:
                ws = self.doc.worksheet(tab_name)
                records = ws.get_all_values()
                if len(records) <= 1:
                    continue

                for r in records[1:]:
                    # Column G: Link Sumber (index 6)
                    if len(r) > 6:
                        norm_u = normalize_url(r[6])
                        if norm_u != "-":
                            self.seen_urls.add(norm_u)
                    # Column B: Judul Lomba (index 1)
                    if len(r) > 1:
                        norm_t = re.sub(r"\W+", "", r[1].lower())
                        if norm_t:
                            self.seen_titles.add(norm_t)

                log.info("Anti-Leak snapshot: loaded tab '%s' (Total unique URLs cached: %d)", tab_name, len(self.seen_urls))
            except Exception:
                continue

    def filter_new(self, items: list[CompetitionItem]) -> list[CompetitionItem]:
        """Secondary filter ensuring in-batch uniqueness and against snapshot."""
        fresh: list[CompetitionItem] = []
        for it in items:
            link = it.source_url
            title_norm = re.sub(r"\W+", "", it.title.lower())

            if link != "-" and link in self.seen_urls:
                log.info("Anti-Leak Dedup: Skipped existing URL -> %s", link)
                continue
            if link == "-" and title_norm in self.seen_titles:
                log.info("Dedup: Skipped duplicate title -> %s", it.title)
                continue

            fresh.append(it)
            if link != "-":
                self.seen_urls.add(link)
            if title_norm:
                self.seen_titles.add(title_norm)

        return fresh

    def append_items(self, items: list[CompetitionItem]) -> int:
        """Batch append competition items with value_input_option='RAW'."""
        if not items or not self.draft_sheet:
            return 0

        rows = [it.to_row() for it in items]
        self.draft_sheet.append_rows(rows, value_input_option="RAW")
        log.info("Appended %d rows to 'DRAFT' worksheet using RAW format.", len(rows))
        return len(rows)
