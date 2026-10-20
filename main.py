#!/usr/bin/env python3
"""Lomba Aggregator & Validator Pipeline (Cakrawala University) - V2 Modular Entrypoint.

Orchestrates:
1. Anti-Leak deduplication snapshot loading from Google Sheets (DRAFT + ARCHIVE).
2. Two-stage scraping from infolomba.id with Pre-Detail date & dedup filters.
3. Rule-based keyword classification into 6 Schools (SEN, SBE, SCD, SPE, SLA, UMUM).
4. Reliable batch append with value_input_option='RAW'.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone

from src.sheets import SheetsSync
from src.sources.infolomba import InfolombaScraper

WIB = timezone(timedelta(hours=7))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s WIB] [%(levelname)s] %(message)s",
    datefmt="%d/%m/%Y %H:%M:%S",
)
logger = logging.getLogger("compScraper-v2")


def run_pipeline(limit: int = 15, max_pages: int = 2, dry_run: bool = False):
    start_time = time.time()
    logger.info("=== Starting Lomba Aggregator Pipeline V2 (Limit=%d, MaxPages=%d, DryRun=%s) ===", limit, max_pages, dry_run)

    # 1. Initialize Sheets Anti-Leak Deduplication Snapshot
    sheets_syncer = None
    existing_urls: set[str] = set()

    if not dry_run:
        sheets_syncer = SheetsSync()
        if not sheets_syncer.client:
            logger.error("Failed initializing Google Sheets. Check SHEET_ID and credentials.")
            sys.exit(1)
        existing_urls = sheets_syncer.seen_urls
        logger.info("Loaded %d existing URLs into Anti-Leak filter from Sheet.", len(existing_urls))
    else:
        logger.info("Dry-run mode: skipping Sheets initialization.")

    # 2. Execute Scraping with Pre-Detail Filtering
    scraper = InfolombaScraper()
    items = scraper.scrape(
        max_items=limit,
        max_pages=max_pages,
        existing_urls=existing_urls,
    )
    logger.info("Scraper collected %d fresh competition items.", len(items))

    if not items:
        logger.info("No new competitions found this run.")
        return

    # 3. Dry-Run or Live Push
    if dry_run:
        output_data = [item.to_dict() for item in items]
        print(json.dumps(output_data, indent=2, ensure_ascii=False))
        logger.info("Dry-run finished in %.2fs. %d items dumped to stdout.", time.time() - start_time, len(items))
        return

    # 4. Secondary Dedup & RAW Batch Append
    filtered_items = sheets_syncer.filter_new(items)
    written_count = sheets_syncer.append_items(filtered_items)

    elapsed = time.time() - start_time
    logger.info(
        "=== Pipeline V2 Completed === Scraped: %d | Filtered Out: %d | Written to DRAFT: %d | Time: %.2fs",
        len(items),
        len(items) - len(filtered_items),
        written_count,
        elapsed,
    )


def main():
    parser = argparse.ArgumentParser(description="Lomba Aggregator & Validator System V2")
    parser.add_argument("--limit", type=int, default=15, help="Maximum items to scrape (default: 15)")
    parser.add_argument("--pages", type=int, default=2, help="Maximum listing pages to scan (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Scrape without writing to Google Sheets")
    args = parser.parse_args()

    run_pipeline(limit=args.limit, max_pages=args.pages, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
