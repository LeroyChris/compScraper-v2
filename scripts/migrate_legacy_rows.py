#!/usr/bin/env python3
"""Migrate legacy 10-column rows (v1 schema) in the audit tab to the 15-column schema.

v1 layout: Scraped At | Judul | Penyelenggara | Rekomendasi School | Biaya |
            Deadline | Link Sumber | Link Pendaftaran | Link Panduan | Status Review

Usage:  python scripts/migrate_legacy_rows.py [--dry-run]
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.sheets import SheetsSync

NEW_ID_RE = re.compile(r"^[a-z_]+_\w+$")
SCHOOLS = {"SEN", "SBE", "SCD", "SPE", "SLA", "UMUM"}


def is_legacy(row: list[str]) -> bool:
    return bool(row) and not NEW_ID_RE.match(row[0].strip())


def to_new(row: list[str]) -> list[str]:
    def at(i: int) -> str:
        return row[i].strip() if i < len(row) else ""

    source_url = at(6)
    slug = source_url.rstrip("/").rsplit("/", 1)[-1]
    digits = re.findall(r"\d+", slug)
    record_id = f"infolomba_{digits[-1]}" if digits else f"legacy_{abs(hash(source_url)) % 10**8}"

    school = at(3).upper()
    if school not in SCHOOLS:
        school = "UMUM"

    status = at(9).upper()
    if status not in {"AUTO_APPROVE", "PERLU_REVIEW", "MANUAL_CHECK"}:
        status = "MANUAL_CHECK"

    return [
        record_id,
        at(1),
        at(2),
        "-",
        "-",
        at(4),
        at(5),
        school,
        "",
        status,
        at(7),
        at(8),
        source_url,
        "",
        at(0),
    ]


def main() -> int:
    dry = "--dry-run" in sys.argv
    sheets = SheetsSync()
    ws = sheets.audit_sheet
    rows = ws.get_all_values()
    targets = [i for i, r in enumerate(rows[1:], start=2) if is_legacy(r)]
    print(f"tab '{ws.title}': {len(targets)} legacy row(s) of {len(rows) - 1}")
    if not targets:
        return 0

    for i in targets:
        new = to_new(rows[i - 1])
        print(f"  row {i}: {rows[i - 1][:3]} -> {new[:3]}")
        if not dry:
            ws.update([new], f"A{i}:O{i}")

    if not dry:
        print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
