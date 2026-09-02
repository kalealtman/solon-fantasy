#!/usr/bin/env python
"""Bulk browser-scraping stopgap while Yahoo Fantasy Sports API access is
pending -- see src/solon_fantasy/scrape.py + league_discovery.py for the
real, API-based scraper this is meant to be replaced by once access clears.
Writes to the same data/processed/*.csv files, so nothing downstream needs
to change when that swap happens.

Reuses the persistent, already-logged-in browser profile from
explore_browser.py, and discovers every season automatically from Yahoo's
own season-switcher dropdown (same "figure it out, don't hand-maintain a
list" spirit as the API version's renew-chain walk -- just via a different
mechanism, since there's no API access to read `renew` from). This does NOT
necessarily reach the league's first-ever season if it was freshly created
that year (no prior season to link back to) -- check the season list it
prints against what you expect.

Every fetched page is cached to data/raw/browser_cache/ (gitignored), so an
interrupted run resumes without re-fetching; delete that folder to force a
clean re-pull. Output is written progressively after each season, so a run
stopped partway through still leaves usable CSVs.

Usage:
    python scripts/run_scrape_browser.py [--league-slug solonfantasyfootball]
        [--start-year 2015] [--end-year 2026] [--skip-rosters]
"""
import argparse
import logging
import re
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from solon_fantasy import scrape_browser as sb  # noqa: E402

PROFILE_DIR = REPO_ROOT / ".browser_profile"
CACHE_DIR = REPO_ROOT / "data" / "raw" / "browser_cache"
OUTPUT_DIR = REPO_ROOT / "data" / "processed"
LEAGUE_SLUG_DEFAULT = "solonfantasyfootball"
POLITENESS_DELAY_SECONDS = 5.0
# Denial backoff is exponential (starting at DENIAL_BACKOFF_BASE_SECONDS,
# doubling each retry, capped at DENIAL_BACKOFF_MAX_SECONDS) so a long
# unattended run can weather a stretch of throttling and resume right where
# it left off once Yahoo eases up, rather than give up after a couple of
# short retries. Worst case across DENIAL_MAX_RETRIES is several hours,
# which is the point for an overnight run.
DENIAL_BACKOFF_BASE_SECONDS = 60
DENIAL_BACKOFF_MAX_SECONDS = 1200
DENIAL_MAX_RETRIES = 30
MAX_EMPTY_WEEKS_STREAK = 2
MAX_WEEK = 18


class RequestDeniedError(RuntimeError):
    """Yahoo returned a bot-detection/rate-limit denial page."""

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--league-slug", default=LEAGUE_SLUG_DEFAULT)
    parser.add_argument("--start-year", type=int, default=None)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument("--skip-rosters", action="store_true", help="Skip the slow team x week roster pull")
    args, unknown = parser.parse_known_args()
    if unknown:
        logger.warning("Ignoring unrecognized arguments: %s", unknown)
    return args


def cache_path(key: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9]+", "_", key).strip("_")
    return CACHE_DIR / f"{safe}.html"


def _looks_denied(html: str) -> bool:
    # "Request denied" is Yahoo's bot-detection/rate-limit stub. The
    # "Will be right back" sad-panda page is a separate, generic Yahoo
    # server-error page (transient 5xx/overload) that doesn't match either
    # of the other signals -- it's plausible-length, valid HTML with no
    # error text obviously related to being blocked, but it's still not the
    # real page and must not be treated (or cached) as a successful, truly-
    # empty result.
    return "Request denied" in html or "Will be right back" in html or len(html) < 500


def fetch(page, url: str, cache_key: str) -> str:
    path = cache_path(cache_key)
    if path.exists():
        cached = path.read_text(encoding="utf-8")
        if not _looks_denied(cached):
            return cached
        # A prior run cached a denial page as if it were real -- don't trust
        # it, re-fetch instead.
        path.unlink()

    for attempt in range(DENIAL_MAX_RETRIES + 1):
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(300)
        html = page.content()
        if not _looks_denied(html):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding="utf-8")
            time.sleep(POLITENESS_DELAY_SECONDS)
            return html
        # Never cache a denial page -- otherwise every future run treats it
        # as a permanent "successful" result for this page.
        if attempt < DENIAL_MAX_RETRIES:
            backoff = min(DENIAL_BACKOFF_BASE_SECONDS * (2 ** attempt), DENIAL_BACKOFF_MAX_SECONDS)
            logger.warning(
                "Yahoo denied the request for %s -- backing off %ds before retry %d/%d",
                url, backoff, attempt + 1, DENIAL_MAX_RETRIES,
            )
            time.sleep(backoff)
    raise RequestDeniedError(f"Yahoo kept denying requests for {url} after {DENIAL_MAX_RETRIES} retries")


def scrape_season(page, slug: str, season: int) -> dict:
    home_html = fetch(page, f"{sb.BASE_URL}/league/{slug}/{season}", f"{season}_home")
    league_id = sb.resolve_league_id(home_html)
    if not league_id:
        logger.warning("Could not resolve league_id for season %s -- skipping", season)
        return {}
    base = f"{sb.BASE_URL}/{season}/f1/{league_id}"

    standings = sb.parse_standings(fetch(page, f"{base}?module=standings&lhst=stand", f"{season}_standings"))
    for r in standings:
        r["season"] = season

    draft = sb.parse_draft(fetch(page, f"{base}/draftresults", f"{season}_draft"))
    for r in draft:
        r["season"] = season

    transactions = []
    offset = 0
    while True:
        suffix = f"&count={offset}" if offset else ""
        html = fetch(page, f"{base}/transactions?transactionsfilter=all{suffix}", f"{season}_transactions_{offset}")
        rows = sb.parse_transactions(html)
        for r in rows:
            r["season"] = season
        transactions.extend(rows)
        if not rows or not sb.has_next_transactions_page(html):
            break
        offset += 25

    matchups = []
    weeks_with_data = []
    empty_streak = 0
    for wk in range(1, MAX_WEEK + 1):
        html = fetch(page, f"{base}?matchup_week={wk}&module=matchups&lhst=matchups", f"{season}_matchups_wk{wk}")
        rows = sb.parse_matchups(html)
        if not rows:
            empty_streak += 1
            if empty_streak >= MAX_EMPTY_WEEKS_STREAK:
                break
            continue
        empty_streak = 0
        weeks_with_data.append(wk)
        for r in rows:
            r["season"] = season
        matchups.extend(rows)

    return {
        "standings": standings,
        "draft": draft,
        "transactions": transactions,
        "matchups": matchups,
        "team_ids": [r["team_id"] for r in standings if r["team_id"]],
        "weeks": weeks_with_data,
        "base": base,
    }


def scrape_rosters(page, season: int, base: str, team_ids: list, weeks: list) -> list:
    rosters = []
    for team_id in team_ids:
        for wk in weeks:
            html = fetch(page, f"{base}/{team_id}/team?week={wk}", f"{season}_roster_{team_id}_wk{wk}")
            for r in sb.parse_roster(html):
                r["season"] = season
                r["week"] = wk
                r["team_id"] = team_id
                rosters.append(r)
    return rosters


def write_csvs(all_rows: dict) -> None:
    """Merge this run's rows into the on-disk CSVs, replacing only the
    seasons this run actually touched -- so scoping a run to e.g. just 2025
    (to backfill a gap) can never wipe out every other already-scraped
    season, the way a blind overwrite would."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, rows in all_rows.items():
        if not rows:
            continue
        out_path = OUTPUT_DIR / f"{name}.csv"
        new_df = pd.DataFrame(rows)
        if out_path.exists():
            existing = pd.read_csv(out_path)
            touched_seasons = set(new_df["season"].unique())
            existing = existing[~existing["season"].isin(touched_seasons)]
            combined = pd.concat([existing, new_df], ignore_index=True)
        else:
            combined = new_df
        combined.to_csv(out_path, index=False)
        logger.info("Wrote %s (%d total rows)", out_path, len(combined))


def main() -> None:
    args = parse_args()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    all_rows = defaultdict(list)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
        page = context.pages[0] if context.pages else context.new_page()

        # Use an explicit, known-good season URL (not the bare slug, whose
        # default-season redirect behavior isn't verified) just to read the
        # season-switcher dropdown -- it lists every other season regardless.
        probe_year = args.end_year or date.today().year
        home_html = fetch(page, f"{sb.BASE_URL}/league/{args.league_slug}/{probe_year}", "seasons_probe")
        seasons = sb.parse_seasons(home_html)
        if not seasons:
            logger.error("Could not find the season list -- are you logged in? (run explore_browser.py first)")
            context.close()
            return
        if args.start_year is not None:
            seasons = [s for s in seasons if s >= args.start_year]
        if args.end_year is not None:
            seasons = [s for s in seasons if s <= args.end_year]
        logger.info("Discovered %d season(s): %s", len(seasons), seasons)

        for season in seasons:
            logger.info("Scraping season %s", season)
            try:
                result = scrape_season(page, args.league_slug, season)
            except RequestDeniedError:
                logger.error(
                    "Yahoo is denying requests even after backoff -- stopping the whole run here "
                    "(not just skipping this season) rather than hammer away at the rest while blocked. "
                    "Wait a while before re-running; already-scraped seasons are saved."
                )
                break
            except Exception:
                logger.error("Failed on season %s", season, exc_info=True)
                continue
            if not result:
                continue

            all_rows["standings"].extend(result["standings"])
            all_rows["draft"].extend(result["draft"])
            all_rows["transactions"].extend(result["transactions"])
            all_rows["matchups"].extend(result["matchups"])

            if not args.skip_rosters:
                try:
                    rosters = scrape_rosters(page, season, result["base"], result["team_ids"], result["weeks"])
                    all_rows["rosters"].extend(rosters)
                except RequestDeniedError:
                    logger.error("Yahoo is denying requests during rosters -- stopping the whole run here.")
                    write_csvs(all_rows)
                    context.close()
                    return
                except Exception:
                    logger.error("Failed on rosters for season %s", season, exc_info=True)

            write_csvs(all_rows)  # progressive save -- a later failure doesn't lose earlier seasons

        context.close()

    write_csvs(all_rows)


if __name__ == "__main__":
    main()
