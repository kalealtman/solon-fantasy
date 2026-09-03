#!/usr/bin/env python
"""One-time backfill: pulls trade transactions for every season into
data/processed/trades.csv. Trades were never in transactions.csv at all --
the main scraper only ever pulled Yahoo's "All Transactions" filter, which
turns out to exclude the separate Trades tab entirely.

Reuses run_scrape_browser's fetch()/caching/denial-backoff, so this is safe
to re-run (already-fetched pages are skipped) and won't hammer Yahoo if
interrupted partway through.

Usage:
    python scripts/backfill_trades.py
"""
import sys
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import run_scrape_browser as rsb  # noqa: E402
from solon_fantasy import scrape_browser as sb  # noqa: E402

LEAGUE_SLUG = "solonfantasyfootball"
SEASON_2014_OVERRIDE = {2014: "492644"}  # not reachable via the slug's season-switcher


def scrape_trades_for_season(page, season: int, league_id: str) -> list:
    base = f"{sb.BASE_URL}/{season}/f1/{league_id}"
    trades = []
    offset = 0
    while True:
        suffix = f"&count={offset}" if offset else ""
        html = rsb.fetch(page, f"{base}/transactions?transactionsfilter=trade{suffix}", f"{season}_trades_{offset}")
        rows = sb.parse_trades(html)
        for r in rows:
            r["season"] = season
        trades.extend(rows)
        if not rows or not sb.has_next_transactions_page(html):
            break
        offset += 25
    return trades


def main() -> None:
    all_trades = []
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(rsb.PROFILE_DIR), headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        probe_html = rsb.fetch(page, f"{sb.BASE_URL}/league/{LEAGUE_SLUG}/2025", "seasons_probe")
        seasons = sb.parse_seasons(probe_html)
        print(f"Discovered seasons: {seasons}")

        season_to_league_id = dict(SEASON_2014_OVERRIDE)
        for season in seasons:
            home_html = rsb.fetch(page, f"{sb.BASE_URL}/league/{LEAGUE_SLUG}/{season}", f"{season}_home")
            league_id = sb.resolve_league_id(home_html)
            if league_id:
                season_to_league_id[season] = league_id
            else:
                print(f"  could not resolve league_id for {season}, skipping")

        for season in sorted(season_to_league_id):
            league_id = season_to_league_id[season]
            print(f"Scraping trades for {season} (league_id={league_id})")
            trades = scrape_trades_for_season(page, season, league_id)
            completed = sum(1 for t in trades if t["completed"]) // 2
            print(f"  {len(trades)} side-rows, {completed} completed trades")
            all_trades.extend(trades)

        context.close()

    out_path = REPO_ROOT / "data" / "processed" / "trades.csv"
    pd.DataFrame(all_trades).to_csv(out_path, index=False)
    print(f"\nwrote {out_path} ({len(all_trades)} rows across {len(season_to_league_id)} seasons)")


if __name__ == "__main__":
    main()
