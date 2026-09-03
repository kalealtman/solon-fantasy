#!/usr/bin/env python
"""Builds owner-level derived stats from the raw per-season CSVs in
data/processed/ -- career records, head-to-head history, and league-wide
highlights ("trophy case" facts). This is the "aggregate the data in an
interesting way" step: standings.csv etc. are organized by season/team, but
a team's *name* changes over the years while its owner doesn't, so anything
asking "who's actually best all-time" needs to roll up by owner first.

Owner identity comes from config/owner_map.csv (team_name -> owner) since
the browser-scraped data has no stable manager GUID the way the (still
pending) API-based scraper would.

Writes:
    data/processed/owner_career.csv   -- one row per owner: seasons played,
        career W-L-T, points for/against, championships, best/worst finish
    data/processed/head_to_head.csv   -- one row per owner pair: all-time
        head-to-head record between them
    data/processed/trophy_case.csv    -- league-wide highlight facts (one
        row per fact, so it's easy to render as a list)

Usage:
    python scripts/build_derived_stats.py
"""
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

PROCESSED_DIR = REPO_ROOT / "data" / "processed"
CONFIG_DIR = REPO_ROOT / "config"


def load_owner_lookup() -> dict:
    owner_map = pd.read_csv(CONFIG_DIR / "owner_map.csv")
    return dict(zip(owner_map["team_name"].str.strip(), owner_map["owner"].str.strip()))


def add_owner_column(df: pd.DataFrame, owner_lookup: dict, name_col: str = "team_name") -> pd.DataFrame:
    df = df.copy()
    df["owner"] = df[name_col].map(owner_lookup)
    unmapped = df[df["owner"].isna()][name_col].unique()
    if len(unmapped):
        print(f"WARNING: no owner mapped for: {list(unmapped)} -- add to config/owner_map.csv")
        df["owner"] = df["owner"].fillna(df[name_col])
    return df


def build_owner_career(standings: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for owner, grp in standings.groupby("owner"):
        championships = int((grp["rank"] == 1).sum())
        second_places = int((grp["rank"] == 2).sum())
        third_places = int((grp["rank"] == 3).sum())
        rows.append(
            {
                "owner": owner,
                "seasons_played": grp["season"].nunique(),
                "first_season": int(grp["season"].min()),
                "last_season": int(grp["season"].max()),
                "career_wins": int(grp["wins"].sum()),
                "career_losses": int(grp["losses"].sum()),
                "career_ties": int(grp["ties"].sum()),
                "win_pct": round(grp["wins"].sum() / max(grp["wins"].sum() + grp["losses"].sum(), 1), 3),
                "career_points_for": round(grp["points_for"].sum(), 2),
                "career_points_against": round(grp["points_against"].sum(), 2),
                "championships": championships,
                "second_places": second_places,
                "third_places": third_places,
                "podiums": championships + second_places + third_places,
                "avg_finish": round(grp["rank"].mean(), 2),
                "best_finish": int(grp["rank"].min()),
                "worst_finish": int(grp["rank"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values(["championships", "win_pct"], ascending=False)


def build_head_to_head(matchups: pd.DataFrame) -> pd.DataFrame:
    """Pair up consecutive rows within each (season, week) -- parse_matchups()
    appends both teams of a game back-to-back, and that order survives the
    CSV round-trip, so row i / row i+1 within a group are always one game."""
    records: dict = {}
    for (_, _), grp in matchups.groupby(["season", "week"]):
        grp = grp.reset_index(drop=True)
        for i in range(0, len(grp) - 1, 2):
            a, b = grp.iloc[i], grp.iloc[i + 1]
            if a["owner"] == b["owner"]:
                continue  # same person on both "teams" (rare data glitch) -- skip
            key = tuple(sorted([a["owner"], b["owner"]]))
            records.setdefault(key, {"wins_a": 0, "wins_b": 0, "ties": 0, "games": 0})
            rec = records[key]
            rec["games"] += 1
            if a["score"] == b["score"]:
                rec["ties"] += 1
            else:
                winner = a["owner"] if a["score"] > b["score"] else b["owner"]
                win_slot = "wins_a" if winner == key[0] else "wins_b"
                rec[win_slot] += 1

    rows = []
    for (owner_a, owner_b), rec in records.items():
        rows.append(
            {
                "owner_a": owner_a,
                "owner_b": owner_b,
                "games": rec["games"],
                f"{owner_a}_wins": rec["wins_a"],
                f"{owner_b}_wins": rec["wins_b"],
                "ties": rec["ties"],
            }
        )
    return pd.DataFrame(rows).sort_values("games", ascending=False)


def is_postseason(season: int, week: int) -> bool:
    """Fantasy playoffs are always the final 3 weeks of the NFL season,
    skipping the actual final week (that week's games are a dead rubber for
    playoff seeding, so the league doesn't play a fantasy week on it): weeks
    14-16 through the 2020 season (16-game/17-week NFL slate), weeks 15-17
    from 2021 on (17-game/18-week slate)."""
    return week in ((14, 15, 16) if season <= 2020 else (15, 16, 17))


def format_tied_names(names) -> str:
    """'A' / 'A & B' / 'A, B & C' -- never silently pick a winner out of a tie."""
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " & " + names[-1]


def build_trophy_case(standings: pd.DataFrame, matchups: pd.DataFrame, transactions: pd.DataFrame) -> pd.DataFrame:
    facts = []

    champs_per_owner = standings[standings["rank"] == 1]["owner"].value_counts()
    if len(champs_per_owner):
        top_count = champs_per_owner.iloc[0]
        leaders = format_tied_names(champs_per_owner[champs_per_owner == top_count].index.tolist())
        facts.append(("Most championships", f"{leaders} ({top_count})"))

    postseason_mask = matchups.apply(lambda r: is_postseason(r["season"], r["week"]), axis=1)
    regular = matchups[~postseason_mask]
    postseason = matchups[postseason_mask]

    for label, subset in [("regular season", regular), ("postseason", postseason)]:
        high = subset.loc[subset["score"].idxmax()]
        facts.append((f"Highest single-week score ({label})", f"{high['owner']} -- {high['score']} (season {high['season']}, week {high['week']})"))

        low = subset.loc[subset["score"].idxmin()]
        facts.append((f"Lowest single-week score ({label})", f"{low['owner']} -- {low['score']} (season {low['season']}, week {low['week']})"))

    best_pf = standings.loc[standings["points_for"].idxmax()]
    facts.append(("Best single-season points total", f"{best_pf['owner']} -- {best_pf['points_for']} ({best_pf['season']})"))

    worst_record = standings.loc[(standings["wins"] / standings[["wins", "losses"]].sum(axis=1)).idxmin()]
    facts.append(("Worst single-season record", f"{worst_record['owner']} -- {worst_record['wins']}-{worst_record['losses']} ({worst_record['season']})"))

    add_counts = transactions[transactions["action"] == "add"]["owner"].value_counts()
    if len(add_counts):
        facts.append(("Most waiver/free-agent adds (career)", f"{add_counts.index[0]} ({add_counts.iloc[0]})"))

    return pd.DataFrame(facts, columns=["fact", "value"])


def main() -> None:
    owner_lookup = load_owner_lookup()

    standings = add_owner_column(pd.read_csv(PROCESSED_DIR / "standings.csv"), owner_lookup)
    matchups = add_owner_column(pd.read_csv(PROCESSED_DIR / "matchups.csv"), owner_lookup)
    transactions = add_owner_column(pd.read_csv(PROCESSED_DIR / "transactions.csv"), owner_lookup)

    owner_career = build_owner_career(standings)
    owner_career.to_csv(PROCESSED_DIR / "owner_career.csv", index=False)
    print(f"wrote owner_career.csv ({len(owner_career)} owners)")

    head_to_head = build_head_to_head(matchups)
    head_to_head.to_csv(PROCESSED_DIR / "head_to_head.csv", index=False)
    print(f"wrote head_to_head.csv ({len(head_to_head)} pairs)")

    trophy_case = build_trophy_case(standings, matchups, transactions)
    trophy_case.to_csv(PROCESSED_DIR / "trophy_case.csv", index=False)
    print(f"wrote trophy_case.csv ({len(trophy_case)} facts)")
    print()
    print(trophy_case.to_string(index=False))


if __name__ == "__main__":
    main()
