#!/usr/bin/env python3
"""Daily Digest — main orchestrator.

Usage:
    python main.py                  # Full run: fetch -> process -> deliver
    python main.py --fetch-only     # Just fetch and print items (debugging)
    python main.py --no-send        # Fetch + process, skip email
    python main.py --preview out.html  # Save HTML preview to file
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from agent.config_loader import load_config
from agent.fetcher import fetch_all_feeds
from agent.processor import process_items
from agent.formatter import format_digest
from agent.deliverer import send_email
from agent.state import SeenTracker
from agent.web import save_web_digest

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("digest")


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    # ── Fetch ─────────────────────────────────────────────
    logger.info("Fetching feeds...")
    all_items: list = []
    for source_name, source_cfg in config["sources"].items():
        feeds = source_cfg.get("feeds", [])
        all_items.extend(fetch_all_feeds(feeds, source_prefix=source_name))

    # Deduplicate across sources
    seen_urls: set[str] = set()
    items: list = []
    for item in all_items:
        if item.url not in seen_urls:
            seen_urls.add(item.url)
            items.append(item)

    if not items:
        logger.warning("No items fetched. Exiting.")
        sys.exit(0)

    logger.info("Fetched %d unique items total", len(items))

    # Filter out previously seen articles
    tracker = SeenTracker()
    fresh_items = [item for item in items if not tracker.is_seen(item.url)]
    logger.info("After filtering seen: %d new items", len(fresh_items))

    if args.fetch_only:
        print(f"\n{'='*60}")
        print(f"FETCHED {len(fresh_items)} NEW ITEMS")
        print(f"{'='*60}\n")
        for i, item in enumerate(fresh_items, 1):
            print(f"{i}. [{item.source}] {item.title}")
            print(f"   {item.url}")
            print(f"   {item.body[:120]}...")
            print()
        return

    if not fresh_items:
        logger.info("No new items since last run. Exiting.")
        return

    # ── Process ───────────────────────────────────────────
    logger.info("Processing with LLM...")
    selected = process_items(fresh_items, config)

    if not selected:
        logger.warning("LLM selected no items. Exiting.")
        return

    logger.info("Selected %d items for digest", len(selected))

    # ── Format ────────────────────────────────────────────
    subject, html = format_digest(selected, config)

    # ── Preview / Deliver ─────────────────────────────────
    if args.preview:
        out_path = Path(args.preview)
        out_path.write_text(html)
        logger.info("Preview saved to %s", out_path)
        print(f"\nSubject: {subject}")
        print(f"Saved HTML preview to: {out_path}")
        tracker.mark_seen([item.url for item in selected])
        return

    if args.web_dir:
        save_web_digest(html, Path(args.web_dir), config, config_path=Path(args.config))
        logger.info("Web digest saved to %s", args.web_dir)

    if args.no_send:
        print(f"\nSubject: {subject}")
        print(f"\n--- Digest ({len(selected)} items) ---")
        for item in selected:
            print(f"  [{item.action_type}] {item.title}")
            print(f"    {item.summary}\n")
    else:
        logger.info("Sending email...")
        try:
            send_email(subject, html, config)
        except Exception:
            if args.web_dir:
                logger.exception("Email delivery failed after web digest was published")
            else:
                raise

    tracker.mark_seen([item.url for item in selected])

    logger.info("Done!")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Daily Digest Agent")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--fetch-only", action="store_true", help="Only fetch and print")
    parser.add_argument("--no-send", action="store_true", help="Process but skip email")
    parser.add_argument("--preview", metavar="FILE", help="Save HTML to file")
    parser.add_argument("--web-dir", metavar="DIR", help="Save dated HTML and update archive index")
    return parser.parse_args()


if __name__ == "__main__":
    main()
