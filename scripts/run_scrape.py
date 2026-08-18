#!/usr/bin/env python
"""CLI entry point: scrape Solon league history from Yahoo and write clean CSVs.

Usage:
    python scripts/run_scrape.py [--start-year 2014] [--end-year 2026]

First run will open a browser for the interactive Yahoo OAuth flow (paste the
verifier code it gives you back into the terminal). The resulting token is
cached to oauth2.json and refreshed automatically on later runs.
"""
import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd
from tqdm.auto import tqdm

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import yahoo_fantasy_api as yfa  # noqa: E402

from solon_fantasy import auth, scrape  # noqa: E402

START_YEAR_DEFAULT = 2014
CONFIG_DIR = REPO_ROOT / "config"
DATA_DIR = REPO_ROOT / "data" / "processed"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=START_YEAR_DEFAULT)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--config-dir", type=Path, default=CONFIG_DIR)
    parser.add_argument("--output-dir", type=Path, default=DATA_DIR)
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    league_ids = scrape.load_league_ids(args.config_dir / "league_ids.txt")
    owner_map = scrape.load_owner_map(args.config_dir / "owner_map.csv")

    session = auth.get_session()
    gm = yfa.Game(session, "nfl")

    all_dfs = defaultdict(list)
    for yr in tqdm(range(args.start_year, args.end_year + 1), desc="Seasons"):
        try:
            year_keys = scrape.league_ids_for_year(gm, yr)
        except Exception:
            logger.warning("No league found for %s (league may not exist yet)", yr, exc_info=True)
            continue

        solon_keys = [k for k in year_keys if k.split(".")[-1] in league_ids]
        for lkey in solon_keys:
            # A full scrape can run well past the ~1hr token lifetime; refresh
            # proactively at each league-season boundary rather than dying mid-run.
            if not session.token_is_valid():
                session.refresh_access_token()
            logger.info("Scraping %s for %s", lkey, yr)
            try:
                data = scrape.scrape_league_season(gm, lkey, yr, owner_map)
            except Exception:
                logger.error("Failed to scrape %s for %s", lkey, yr, exc_info=True)
                continue
            for name, df in data.items():
                if df is not None and not df.empty:
                    all_dfs[name].append(df)
            time.sleep(0.5)  # be polite to Yahoo's rate limits

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, frames in all_dfs.items():
        combined = pd.concat(frames, ignore_index=True)
        out_path = args.output_dir / f"{name}.csv"
        combined.to_csv(out_path, index=False)
        logger.info("Wrote %s (%d rows)", out_path, len(combined))


if __name__ == "__main__":
    main()
