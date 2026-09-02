#!/usr/bin/env python
"""Builds the interactive site: combines site/template.html + site/app.js
with a fresh JSON export of data/processed/*.csv into one self-contained
HTML file. Re-run this any time the underlying data changes (new season,
backfill, etc.) -- the output isn't checked into git since it's just the
source data + template baked together and gets stale the moment either
changes.

Usage:
    python scripts/build_site.py [--output site/dist/solon_site.html]
"""
import argparse
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
DEFAULT_OUTPUT = SITE_DIR / "dist" / "solon_site.html"

# rosters.csv is deliberately excluded -- it's ~15x the size of everything
# else combined and the site doesn't have a per-player view yet.
DATASETS = ["standings", "draft", "matchups", "transactions", "owner_career", "head_to_head", "trophy_case"]


def build_data_json() -> str:
    data = {}
    for name in DATASETS:
        df = pd.read_csv(PROCESSED_DIR / f"{name}.csv")
        df = df.where(pd.notnull(df), None)
        data[name] = df.to_dict(orient="records")
    return json.dumps(data, separators=(",", ":"))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    template = (SITE_DIR / "template.html").read_text(encoding="utf-8")
    app_js = (SITE_DIR / "app.js").read_text(encoding="utf-8")
    data_json = build_data_json().replace("</script", "<\\/script")

    html = template.replace("__LEAGUE_DATA_JSON__", data_json).replace("__APP_JS__", app_js)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(html, encoding="utf-8")
    print(f"wrote {args.output} ({args.output.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
