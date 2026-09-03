#!/usr/bin/env python
"""Aggregates the end-of-season "GM Coaches Poll" Google Form export into the
site's data files.

The form asks every manager to anonymously rank every other GM 1 (best) to N
(worst) on overall GM skill, plus vote on a handful of superlative awards. The
form's own text promises responses are recorded anonymously and not tied to
results, so this script (and the site) only ever surfaces aggregates -- who
ranked whom is never written to a committed file or rendered anywhere.

Input is one .xlsx export per season (named like
"2025 Solon Fantasy GM Coaches Poll (Responses).xlsx" -- the leading year is
read as the season). Not committed to git; read directly from wherever it
lands, then discarded once this script has run.

Usage:
    python scripts/build_coaches_poll.py "2025 Solon Fantasy GM Coaches Poll (Responses).xlsx" [more.xlsx ...]
"""
import argparse
import re
import statistics
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = REPO_ROOT / "data" / "processed"
CONFIG_DIR = REPO_ROOT / "config"

CANDIDATE_PREFIX = "The Coaches' Poll ["
NON_AWARD_COLUMNS = {"Timestamp", "Select Your Name"}


def format_tied_names(names) -> str:
    """'A' / 'A & B' / 'A, B & C' -- never silently pick a winner out of a tie."""
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " & " + names[-1]


def season_from_filename(path: Path) -> int:
    match = re.search(r"(20\d{2})", path.name)
    if not match:
        raise ValueError(f"Can't find a season year in filename: {path.name}")
    return int(match.group(1))


def build_rankings(season: int, responses: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    candidate_cols = [c for c in responses.columns if c.startswith(CANDIDATE_PREFIX)]
    n_candidates = len(candidate_cols)
    rows = []
    for col in candidate_cols:
        owner = col[len(CANDIDATE_PREFIX) : -1]
        ranks = responses[col].dropna().tolist()
        if not ranks:
            continue
        points = sum(n_candidates - r for r in ranks)
        rows.append(
            {
                "season": season,
                "owner": owner,
                "points": points,
                "first_place_votes": sum(1 for r in ranks if r == 1),
                "highest_rank": int(min(ranks)),
                "lowest_rank": int(max(ranks)),
                "median_rank": statistics.median(ranks),
                "avg_rank": statistics.mean(ranks),
                "num_votes": len(ranks),
            }
        )
    df = pd.DataFrame(rows).sort_values("points", ascending=False).reset_index(drop=True)
    # Competition ranking (1, 2, 2, 4, ...) -- ties share a rank rather than
    # an arbitrary tiebreak deciding who "really" placed higher.
    df["rank"] = df["points"].rank(ascending=False, method="min").astype(int)
    df = df[["season", "rank", "owner", "points", "first_place_votes", "highest_rank", "lowest_rank", "median_rank", "avg_rank", "num_votes"]]
    return df, n_candidates


def build_awards(season: int, responses: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    candidate_cols = {c for c in responses.columns if c.startswith(CANDIDATE_PREFIX)}
    award_cols = [c for c in responses.columns if c not in candidate_cols and c not in NON_AWARD_COLUMNS]
    rows = []
    for col in award_cols:
        votes = responses[col].dropna()
        if votes.empty:
            continue
        counts = votes.value_counts()
        top_count = int(counts.max())
        winners = format_tied_names(counts[counts == top_count].index.tolist())
        runners_up = counts[counts < top_count]
        runner_up_detail = "; ".join(f"{name} ({n})" for name, n in runners_up.items())
        info = meta.get(col, {})
        rows.append(
            {
                "season": season,
                "award": col,
                "description": info.get("description", ""),
                "image_slug": info.get("image_slug", ""),
                "emoji": info.get("emoji", "🏆"),
                "winner": winners,
                "votes": top_count,
                "total_votes_cast": int(votes.shape[0]),
                "runner_up_detail": runner_up_detail,
            }
        )
    return pd.DataFrame(rows)


def load_award_meta() -> dict:
    path = CONFIG_DIR / "coaches_poll_awards.csv"
    if not path.exists():
        return {}
    df = pd.read_csv(path).fillna("")
    return {row["award"]: row.to_dict() for _, row in df.iterrows()}


def merge_by_season(path: Path, new_df: pd.DataFrame) -> pd.DataFrame:
    if path.exists():
        existing = pd.read_csv(path)
        existing = existing[~existing["season"].isin(new_df["season"].unique())]
        new_df = pd.concat([existing, new_df], ignore_index=True)
    return new_df.sort_values("season")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xlsx_paths", nargs="+", type=Path)
    args, _unknown = parser.parse_known_args()

    award_meta = load_award_meta()
    all_rankings = []
    all_awards = []
    meta_rows = []

    for path in args.xlsx_paths:
        season = season_from_filename(path)
        responses = pd.read_excel(path, sheet_name="Form Responses 1")
        rankings, n_candidates = build_rankings(season, responses)
        awards = build_awards(season, responses, award_meta)
        all_rankings.append(rankings)
        all_awards.append(awards)
        meta_rows.append({"season": season, "num_candidates": n_candidates, "num_respondents": len(responses)})
        print(f"{path.name}: season {season}, {len(responses)} respondents, {n_candidates} candidates, {len(awards)} awards")

    rankings_path = PROCESSED_DIR / "coaches_poll_rankings.csv"
    awards_path = PROCESSED_DIR / "coaches_poll_awards.csv"
    meta_path = PROCESSED_DIR / "coaches_poll_meta.csv"

    merge_by_season(rankings_path, pd.concat(all_rankings, ignore_index=True)).to_csv(rankings_path, index=False)
    merge_by_season(awards_path, pd.concat(all_awards, ignore_index=True)).to_csv(awards_path, index=False)
    merge_by_season(meta_path, pd.DataFrame(meta_rows)).to_csv(meta_path, index=False)
    print(f"wrote {rankings_path}, {awards_path}, {meta_path}")


if __name__ == "__main__":
    main()
