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


def top_drafted_players(draft: pd.DataFrame, owner: str, n: int = 3) -> str:
    """'Player A (4x); Player B (3x); Player C (2x)' -- count desc, name asc
    as a deterministic tiebreak. A tie exactly at the n-th spot can expand
    or shrink the list by one; that's normal/expected for a "top N" cutoff,
    unlike a single "most drafted" fact where a silent tie-break would be
    misleading."""
    picks = draft[draft["owner"] == owner]
    if picks.empty:
        return ""
    counts = picks["player_name"].value_counts().rename_axis("player_name").reset_index(name="count")
    ranked = counts.sort_values(["count", "player_name"], ascending=[False, True]).head(n)
    return "; ".join(f"{row.player_name} ({row.count}x)" for row in ranked.itertuples())


def build_owner_career(
    standings: pd.DataFrame,
    transactions: pd.DataFrame,
    draft: pd.DataFrame,
    postseason_records: pd.DataFrame,
    trades: pd.DataFrame = None,
) -> pd.DataFrame:
    txn_counts = transactions.groupby("owner")["action"].value_counts().unstack(fill_value=0)
    postseason_totals = postseason_records.groupby("owner")[["wins", "losses", "ties"]].sum() if len(postseason_records) else None
    completed_trades = trades[trades["completed"]] if trades is not None and len(trades) else None
    trade_counts = completed_trades["owner"].value_counts() if completed_trades is not None else None

    rows = []
    for owner, grp in standings.groupby("owner"):
        championships = int((grp["rank"] == 1).sum())
        second_places = int((grp["rank"] == 2).sum())
        third_places = int((grp["rank"] == 3).sum())
        playoff_appearances = int(grp["made_playoffs"].sum())
        seasons_played = grp["season"].nunique()
        adds = int(txn_counts["add"].get(owner, 0)) if "add" in txn_counts.columns else 0
        drops = int(txn_counts["drop"].get(owner, 0)) if "drop" in txn_counts.columns else 0
        top_players = top_drafted_players(draft, owner)
        ps_wins = int(postseason_totals["wins"].get(owner, 0)) if postseason_totals is not None else 0
        ps_losses = int(postseason_totals["losses"].get(owner, 0)) if postseason_totals is not None else 0
        ps_ties = int(postseason_totals["ties"].get(owner, 0)) if postseason_totals is not None else 0
        trades_count = int(trade_counts.get(owner, 0)) if trade_counts is not None else 0
        rows.append(
            {
                "owner": owner,
                "seasons_played": seasons_played,
                "first_season": int(grp["season"].min()),
                "last_season": int(grp["season"].max()),
                "career_wins": int(grp["wins"].sum()),
                "career_losses": int(grp["losses"].sum()),
                "career_ties": int(grp["ties"].sum()),
                "win_pct": round(grp["wins"].sum() / max(grp["wins"].sum() + grp["losses"].sum(), 1), 3),
                "career_points_for": round(grp["points_for"].sum(), 2),
                "career_points_against": round(grp["points_against"].sum(), 2),
                "pf_per_season": round(grp["points_for"].sum() / seasons_played, 1),
                "pa_per_season": round(grp["points_against"].sum() / seasons_played, 1),
                "playoff_appearances": playoff_appearances,
                "championships": championships,
                "second_places": second_places,
                "third_places": third_places,
                "podiums": championships + second_places + third_places,
                "avg_finish": round(grp["rank"].mean(), 2),
                "best_finish": int(grp["rank"].min()),
                "worst_finish": int(grp["rank"].max()),
                "career_adds": adds,
                "career_drops": drops,
                "career_transactions": adds + drops,
                "transactions_per_season": round((adds + drops) / seasons_played, 1),
                "career_trades": trades_count,
                "trades_per_season": round(trades_count / seasons_played, 1),
                "postseason_wins": ps_wins,
                "postseason_losses": ps_losses,
                "postseason_ties": ps_ties,
                "postseason_win_pct": round(ps_wins / max(ps_wins + ps_losses, 1), 3),
                "top_drafted_players": top_players,
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


def build_postseason_records(matchups: pd.DataFrame, standings: pd.DataFrame) -> pd.DataFrame:
    """One row per (owner, season): that season's CHAMPIONSHIP-BRACKET-ONLY
    postseason W-L-T. Yahoo runs a consolation bracket in parallel with the
    real playoffs during the same weeks, for teams that didn't make the
    playoffs -- without restricting to standings.made_playoffs, this would
    count consolation-bracket wins/losses as if they were real postseason
    games. Also needed for single-season best/worst postseason facts -- a
    plain career total would hide e.g. someone going 3-0 one year and 0-3
    another."""
    made_playoffs = {(row["season"], row["team_name"]): row["made_playoffs"] for _, row in standings.iterrows()}

    postseason = matchups[matchups.apply(lambda r: is_postseason(r["season"], r["week"]), axis=1)]
    records: dict = {}
    for (season, _week), grp in postseason.groupby(["season", "week"]):
        grp = grp.reset_index(drop=True)
        for i in range(0, len(grp) - 1, 2):
            a, b = grp.iloc[i], grp.iloc[i + 1]
            if a["owner"] == b["owner"]:
                continue
            if not (made_playoffs.get((season, a["team_name"])) and made_playoffs.get((season, b["team_name"]))):
                continue  # at least one side is in the consolation bracket, not the real playoffs
            for owner, own_score, opp_score in ((a["owner"], a["score"], b["score"]), (b["owner"], b["score"], a["score"])):
                key = (owner, season)
                records.setdefault(key, {"wins": 0, "losses": 0, "ties": 0})
                if own_score > opp_score:
                    records[key]["wins"] += 1
                elif own_score < opp_score:
                    records[key]["losses"] += 1
                else:
                    records[key]["ties"] += 1
    rows = [{"owner": owner, "season": season, **rec} for (owner, season), rec in records.items()]
    return pd.DataFrame(rows, columns=["owner", "season", "wins", "losses", "ties"])


def format_tied_names(names) -> str:
    """'A' / 'A & B' / 'A, B & C' -- never silently pick a winner out of a tie."""
    names = sorted(names)
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " & " + names[-1]


def build_trophy_case(
    standings: pd.DataFrame,
    matchups: pd.DataFrame,
    transactions: pd.DataFrame,
    postseason_records: pd.DataFrame,
    trades: pd.DataFrame = None,
) -> pd.DataFrame:
    """Each record is (category, fact, number, name, detail) -- kept as
    separate fields, rather than one packed string, specifically so the
    number can be styled larger/more prominent than the name on the card."""
    facts = []  # list of dicts: category, fact, number, name, detail

    def add_fact(category, fact, number, name, detail=""):
        facts.append({"category": category, "fact": fact, "number": number, "name": name, "detail": detail})

    champs_per_owner = standings[standings["rank"] == 1]["owner"].value_counts()
    if len(champs_per_owner):
        top_count = champs_per_owner.iloc[0]
        leaders = format_tied_names(champs_per_owner[champs_per_owner == top_count].index.tolist())
        add_fact("regular_season", "Most Championships", str(top_count), leaders)

    best_pf = standings.loc[standings["points_for"].idxmax()]
    add_fact("regular_season", "Best Single-Season Points Total", str(best_pf["points_for"]), best_pf["owner"], str(best_pf["season"]))

    worst_record = standings.loc[(standings["wins"] / standings[["wins", "losses"]].sum(axis=1)).idxmin()]
    add_fact(
        "regular_season",
        "Worst Single-Season Record",
        f"{worst_record['wins']}-{worst_record['losses']}",
        worst_record["owner"],
        str(worst_record["season"]),
    )

    postseason_mask = matchups.apply(lambda r: is_postseason(r["season"], r["week"]), axis=1)
    regular = matchups[~postseason_mask]
    postseason = matchups[postseason_mask]

    for category, subset in [("regular_season", regular), ("postseason", postseason)]:
        high = subset.loc[subset["score"].idxmax()]
        add_fact(category, "Highest Single-Week Score", str(high["score"]), high["owner"], f"season {high['season']}, week {high['week']}")

        low = subset.loc[subset["score"].idxmin()]
        add_fact(category, "Lowest Single-Week Score", str(low["score"]), low["owner"], f"season {low['season']}, week {low['week']}")

    if len(postseason_records):
        # Cumulative (career) record, not single-season -- with only 2-3
        # games a postseason, *someone* goes 3-0 and *someone* goes 0-3
        # basically every year, which makes the single-season version of
        # this fact meaningless (it never highlights anything unusual).
        career_pr = postseason_records.groupby("owner")[["wins", "losses"]].sum().reset_index()
        career_pr["win_pct"] = career_pr["wins"] / career_pr[["wins", "losses"]].sum(axis=1).clip(lower=1)

        def record_fact(label, ascending):
            ranked = career_pr.sort_values(["win_pct", "wins"], ascending=ascending)
            top = ranked.iloc[0]
            tied = career_pr[(career_pr["wins"] == top["wins"]) & (career_pr["losses"] == top["losses"])]
            add_fact(
                "postseason",
                label,
                f"{int(top['wins'])}-{int(top['losses'])}",
                format_tied_names(tied["owner"].tolist()),
            )

        record_fact("Best Career Postseason Record", ascending=False)
        record_fact("Worst Career Postseason Record", ascending=True)

    add_counts = transactions[transactions["action"] == "add"]["owner"].value_counts()
    if len(add_counts):
        add_fact("transactions", "Most Waiver/FA Adds (Career)", str(add_counts.iloc[0]), add_counts.index[0])

    drop_counts = transactions[transactions["action"] == "drop"]["owner"].value_counts()
    if len(drop_counts):
        add_fact("transactions", "Most Drops (Career)", str(drop_counts.iloc[0]), drop_counts.index[0])

    total_counts = transactions["owner"].value_counts()
    if len(total_counts):
        add_fact("transactions", "Most Total Transactions (Career)", str(total_counts.iloc[0]), total_counts.index[0])

    if trades is not None and len(trades):
        completed = trades[trades["completed"]]
        trade_counts = completed["owner"].value_counts()
        if len(trade_counts):
            add_fact("transactions", "Most Trades (Career)", str(trade_counts.iloc[0]), trade_counts.index[0])

    return pd.DataFrame(facts, columns=["category", "fact", "number", "name", "detail"])


def main() -> None:
    owner_lookup = load_owner_lookup()

    standings = add_owner_column(pd.read_csv(PROCESSED_DIR / "standings.csv"), owner_lookup)
    matchups = add_owner_column(pd.read_csv(PROCESSED_DIR / "matchups.csv"), owner_lookup)
    transactions = add_owner_column(pd.read_csv(PROCESSED_DIR / "transactions.csv"), owner_lookup)
    draft = add_owner_column(pd.read_csv(PROCESSED_DIR / "draft.csv"), owner_lookup)

    trades_path = PROCESSED_DIR / "trades.csv"
    trades = add_owner_column(pd.read_csv(trades_path), owner_lookup) if trades_path.exists() else None

    postseason_records = build_postseason_records(matchups, standings)

    owner_career = build_owner_career(standings, transactions, draft, postseason_records, trades)
    owner_career.to_csv(PROCESSED_DIR / "owner_career.csv", index=False)
    print(f"wrote owner_career.csv ({len(owner_career)} owners)")

    head_to_head = build_head_to_head(matchups)
    head_to_head.to_csv(PROCESSED_DIR / "head_to_head.csv", index=False)
    print(f"wrote head_to_head.csv ({len(head_to_head)} pairs)")

    trophy_case = build_trophy_case(standings, matchups, transactions, postseason_records, trades)
    trophy_case.to_csv(PROCESSED_DIR / "trophy_case.csv", index=False)
    print(f"wrote trophy_case.csv ({len(trophy_case)} facts)")
    print()
    print(trophy_case.to_string(index=False))


if __name__ == "__main__":
    main()
