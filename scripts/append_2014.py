#!/usr/bin/env python
"""One-time backfill for the 2014 season, which isn't reachable through the
solonfantasyfootball slug's season-switcher/renewal chain (2014 was either a
freshly-created league that year or has since been renamed/re-slugged) --
league_id 492644 confirmed by hand against the old repo's own historical
records rather than auto-discovered.

Reuses run_scrape_browser's fetch()/caching/denial-backoff and
scrape_browser's parsers -- this is not meant to become a recurring script,
just a single append. Appending is idempotent: rerunning replaces any
existing 2014 rows rather than duplicating them.

Usage:
    python scripts/append_2014.py
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

SEASON = 2014
LEAGUE_ID = "492644"
BASE = f"{sb.BASE_URL}/{SEASON}/f1/{LEAGUE_ID}"


def append_csv(name: str, rows: list) -> None:
    if not rows:
        print(f"no {name} rows for {SEASON} -- skipping")
        return
    path = rsb.OUTPUT_DIR / f"{name}.csv"
    new_df = pd.DataFrame(rows)
    if path.exists():
        existing = pd.read_csv(path)
        existing = existing[existing["season"] != SEASON]  # replace, don't duplicate, on rerun
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_csv(path, index=False)
    print(f"wrote {path} ({len(combined)} total rows, {len(new_df)} new for {SEASON})")


def main() -> None:
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(rsb.PROFILE_DIR), headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        home_html = rsb.fetch(page, BASE, f"{SEASON}_home")
        if rsb._looks_denied(home_html):
            print(f"Could not load {BASE} -- wrong league_id, or not logged in. Aborting.")
            context.close()
            return

        standings = sb.parse_standings(rsb.fetch(page, f"{BASE}?module=standings&lhst=stand", f"{SEASON}_standings"))
        for r in standings:
            r["season"] = SEASON

        draft = sb.parse_draft(rsb.fetch(page, f"{BASE}/draftresults", f"{SEASON}_draft"))
        for r in draft:
            r["season"] = SEASON

        transactions = []
        offset = 0
        while True:
            suffix = f"&count={offset}" if offset else ""
            html = rsb.fetch(page, f"{BASE}/transactions?transactionsfilter=all{suffix}", f"{SEASON}_transactions_{offset}")
            rows = sb.parse_transactions(html)
            for r in rows:
                r["season"] = SEASON
            transactions.extend(rows)
            if not rows or not sb.has_next_transactions_page(html):
                break
            offset += 25

        matchups = []
        weeks_with_data = []
        empty_streak = 0
        for wk in range(1, rsb.MAX_WEEK + 1):
            html = rsb.fetch(page, f"{BASE}?matchup_week={wk}&module=matchups&lhst=matchups", f"{SEASON}_matchups_wk{wk}")
            rows = sb.parse_matchups(html)
            if not rows:
                empty_streak += 1
                if empty_streak >= rsb.MAX_EMPTY_WEEKS_STREAK:
                    break
                continue
            empty_streak = 0
            weeks_with_data.append(wk)
            for r in rows:
                r["season"] = SEASON
            matchups.extend(rows)

        team_ids = [r["team_id"] for r in standings if r["team_id"]]
        rosters = rsb.scrape_rosters(page, SEASON, BASE, team_ids, weeks_with_data)

        context.close()

    print(f"\nDiscovered {len(standings)} teams, {len(weeks_with_data)} weeks with matchups for {SEASON}\n")
    append_csv("standings", standings)
    append_csv("draft", draft)
    append_csv("transactions", transactions)
    append_csv("matchups", matchups)
    append_csv("rosters", rosters)


if __name__ == "__main__":
    main()
