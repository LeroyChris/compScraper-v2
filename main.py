#!/usr/bin/env python3
"""Lomba Aggregator pipeline.

Flow: Sheets anti-leak snapshot -> scrape every source -> validate -> dedup ->
classify -> append to the audit tab.

Everything stops at the sheet; approval and Instagram posting happen downstream.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time

from src.classifier import CompetitionClassifier
from src.config import MAX_ITEMS_PER_RUN, MAX_PAGES
from src.dedupe import Deduplicator
from src.models import CompetitionRecord
from src.sheets import SheetsSync
from src.sources import build_sources

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)-7s %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("compScraper-v2")


def run_pipeline(limit: int = MAX_ITEMS_PER_RUN, dry_run: bool = False, source_filter: str | None = None) -> int:
    started = time.time()

    sheets = None
    known_urls: set[str] = set()
    known_entries: list[tuple[str, str | None]] = []

    if not dry_run:
        sheets = SheetsSync()
        if not sheets.client:
            log.error("Cannot reach Google Sheets. Check SHEET_ID + credentials.")
            return 1
        known_urls = sheets.seen_urls
        known_entries = sheets.seen_entries
        log.info("Anti-leak snapshot: %d urls, %d titles", len(known_urls), len(known_entries))
    else:
        log.info("Dry run: Sheets disabled.")

    raw: list[CompetitionRecord] = []
    for scraper in build_sources():
        if source_filter and scraper.source_id != source_filter:
            continue
        log.info("=== %s (%s) ===", scraper.source_name, scraper.source_id)
        try:
            items = scraper.scrape(limit=limit, known_urls=known_urls)
        except Exception as exc:
            log.error("Source %s failed: %s", scraper.source_id, exc, exc_info=True)
            continue
        log.info("%s: %d records", scraper.source_id, len(items))
        raw.extend(items)

    log.info("Scraped %d raw records", len(raw))

    classifier = CompetitionClassifier()
    validated: list[CompetitionRecord] = []
    for record in raw:
        enriched = classifier.enrich(record)
        if enriched is not None:
            validated.append(enriched)
    log.info("%d records survived the noise filter", len(validated))

    deduper = Deduplicator(known_urls=known_urls, known_entries=known_entries)
    fresh = deduper.filter_new(validated)
    log.info("%d records after dedup", len(fresh))

    if dry_run:
        print(json.dumps([r.to_dict() for r in fresh], indent=2, ensure_ascii=False))
        return 0

    if not fresh:
        log.info("Nothing new to write.")
        return 0

    written = sheets.append_items(fresh)
    sheets.write_local_copy(fresh)
    log.info("Wrote %d rows to the audit tab in %.1fs", written, time.time() - started)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lomba Aggregator -> Google Sheets")
    parser.add_argument("--limit", type=int, default=MAX_ITEMS_PER_RUN)
    parser.add_argument("--pages", type=int, default=MAX_PAGES, help="kept for CLI compatibility")
    parser.add_argument("--source", dest="source", help="only run one source id")
    parser.add_argument("--dry-run", action="store_true", help="scrape without writing to Sheets")
    args = parser.parse_args()
    return run_pipeline(limit=args.limit, dry_run=args.dry_run, source_filter=args.source)


if __name__ == "__main__":
    sys.exit(main())
