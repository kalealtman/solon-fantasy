#!/usr/bin/env python
"""CLI entry point: scrape Solon league history from Yahoo and write clean CSVs.

Usage:
    python scripts/run_scrape.py [--league-name Solon] [--start-year 2014] [--end-year 2026]

League-seasons are discovered automatically by walking Yahoo's renew chain
backward from the most recent season matching --league-name -- see
src/solon_fantasy/league_discovery.py. No yearly config edits needed; a
brand-new season is picked up the moment it exists on Yahoo. If the chain
can't reach a season (e.g. the league's first-ever year), add it manually to
config/league_id_overrides.txt.

First run will open a browser for the interactive Yahoo OAuth flow (paste the
verifier code it gives you back into the terminal). The resulting token is
cached to oauth2.json and refreshed automatically on later runs.
"""
import argparse
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path

import pandas as pd
from tqdm.auto import tqdm

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import yahoo_fantasy_api as yfa  # noqa: E402

from solon_fantasy import auth, config_io, league_discovery, scrape  # noqa: E402

LEAGUE_NAME_DEFAULT = "Solon"
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--league-name", default=LEAGUE_NAME_DEFAULT, help="Substring to match the league name on")
    parser.add_argument("--start-year", type=int, default=None, help="Restrict to seasons >= this year")
    parser.add_argument("--end-year", type=int, default=None, help="Restrict to seasons <= this year")
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    args, unknown = parser.parse_known_args()
    if unknown:
        # Running under a Jupyter/IPython kernel injects its own args (e.g.
        # --f=...kernel-...json) into sys.argv; ignore those rather than
        # dying, but still surface anything that looks like a real typo.
        logger.warning("Ignoring unrecognized arguments: %s", unknown)
    return args


def main() -> None:
    args = parse_args()

    legacy_owner_map = config_io.load_owner_map(args.config_dir / "owner_map.csv")
    owners_path = args.config_dir / "owners.csv"
    owners_map = config_io.load_owners_map(owners_path)
    overrides = config_io.load_league_overrides(args.config_dir / "league_id_overrides.txt")

    session = auth.get_session()
    gm = yfa.Game(session, "nfl")

    chain = league_discovery.discover_league_chain(gm, args.league_name)
    chain.update(overrides)  # overrides fill gaps the renew chain can't reach

    seasons = sorted(chain)
    if args.start_year is not None:
        seasons = [s for s in seasons if s >= args.start_year]
    if args.end_year is not None:
        seasons = [s for s in seasons if s <= args.end_year]
    logger.info("Discovered %d season(s): %s", len(seasons), seasons)

    all_dfs = defaultdict(list)
    for season in tqdm(seasons, desc="Seasons"):
        lkey = chain[season]
        # A full scrape can run well past the ~1hr token lifetime; refresh
        # proactively at each league-season boundary rather than dying mid-run.
        if not session.token_is_valid():
            session.refresh_access_token()
        logger.info("Scraping %s for %s", lkey, season)
        try:
            data = scrape.scrape_league_season(gm, lkey, season, owners_map, legacy_owner_map)
        except Exception:
            logger.error("Failed to scrape %s for %s", lkey, season, exc_info=True)
            continue
        for name, df in data.items():
            if df is not None and not df.empty:
                all_dfs[name].append(df)
        time.sleep(0.5)  # be polite to Yahoo's rate limits

    config_io.save_owners_map(owners_path, owners_map)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frames in all_dfs.items():
        combined = pd.concat(frames, ignore_index=True)
        out_path = args.output_dir / f"{name}.csv"
        combined.to_csv(out_path, index=False)
        logger.info("Wrote %s (%d rows)", out_path, len(combined))


if __name__ == "__main__":
    main()
