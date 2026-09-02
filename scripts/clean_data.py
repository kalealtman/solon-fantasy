#!/usr/bin/env python
"""Normalizes text in data/processed/*.csv: Yahoo renders the same
underlying name inconsistently depending on the page (a straight apostrophe
on one page, a "smart" curly one on another), which fragments any
groupby/aggregation on a name column since e.g. "Jackson's Team" and
"Jackson's Team" (curly) would otherwise count as two different teams.

Idempotent -- safe to re-run any time after a fresh scrape.

Usage:
    python scripts/clean_data.py
"""
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"

REPLACEMENTS = {
    "’": "'",  # curly right single quote -> straight apostrophe
    "‘": "'",  # curly left single quote  -> straight apostrophe
    "“": '"',  # curly left double quote  -> straight quote
    "”": '"',  # curly right double quote -> straight quote
}


def normalize(value):
    if not isinstance(value, str):
        return value
    for bad, good in REPLACEMENTS.items():
        value = value.replace(bad, good)
    return value.strip()


def main() -> None:
    for path in sorted(PROCESSED_DIR.glob("*.csv")):
        df = pd.read_csv(path)
        changed = 0
        for col in df.select_dtypes(include="object").columns:
            before = df[col].copy()
            df[col] = df[col].map(normalize)
            changed += int((before != df[col]).sum())
        df.to_csv(path, index=False)
        print(f"{path.name}: normalized {changed} cell(s)")


if __name__ == "__main__":
    main()
