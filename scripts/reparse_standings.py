#!/usr/bin/env python
"""One-time re-parse of standings.csv to add the made_playoffs column,
which scrape_browser.parse_standings() didn't originally capture (Yahoo
marks a clinched playoff spot with a "*" prefix on the rank, which the old
parser stripped along with the rest of the non-digit characters).

Re-reads the already-cached standings HTML in data/raw/browser_cache/
directly -- no network calls, no re-scraping needed.

Usage:
    python scripts/reparse_standings.py
"""
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from solon_fantasy import scrape_browser as sb  # noqa: E402

CACHE_DIR = REPO_ROOT / "data" / "raw" / "browser_cache"
OUT_PATH = REPO_ROOT / "data" / "processed" / "standings.csv"


def main() -> None:
    rows = []
    for path in sorted(CACHE_DIR.glob("*_standings.html")):
        season = int(path.name.split("_")[0])
        if season == 2026:
            # 2026's league page redirected to 2025's completed standings when
            # this was originally fetched (before the 2026 draft had happened) --
            # this file is mislabeled 2025 data, not real 2026 data. Excluded
            # from the main pipeline for the same reason.
            continue
        html = path.read_text(encoding="utf-8")
        for r in sb.parse_standings(html):
            r["season"] = season
            rows.append(r)

    new_df = pd.DataFrame(rows)
    if OUT_PATH.exists():
        existing = pd.read_csv(OUT_PATH)
        existing = existing[~existing["season"].isin(new_df["season"].unique())]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df
    combined.to_csv(OUT_PATH, index=False)
    print(f"wrote {OUT_PATH} ({len(combined)} rows, {new_df['season'].nunique()} seasons re-parsed)")
    print(f"made_playoffs value counts:\n{combined['made_playoffs'].value_counts()}")


if __name__ == "__main__":
    main()
