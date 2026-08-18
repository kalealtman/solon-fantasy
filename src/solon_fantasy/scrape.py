"""Pulls standings, draft, managers, matchups, transactions, and rosters for
one Yahoo fantasy football league-season at a time.

API-level pulls are cached individually (keyed on league key / week / team
key, never on the live `gm`/`yfa.Game` session object) so an interrupted
scrape can be re-run and will only re-fetch what it hasn't already pulled.
"""
import logging
import warnings
from functools import lru_cache
from typing import Dict, List, Optional

import objectpath
import pandas as pd
import yahoo_fantasy_api as yfa

from .cache import CACHE

logger = logging.getLogger(__name__)

TRANSACTION_TYPES = "add,drop,commish,trade"


def resolve_owner(
    guid: Optional[str],
    nickname: Optional[str],
    team_name: str,
    owners_map: Dict[str, str],
    legacy_owner_map: Dict[str, str],
) -> str:
    """Resolve a team to a human owner name, preferring the stable manager
    GUID over anything name-based (team names change every season; nicknames
    can too; a GUID is the same person forever).

    `owners_map` (guid -> display_name) is mutated in place: an unseen GUID
    gets auto-added using whatever nickname Yahoo gave us, so it only needs a
    manual fix (editing the display_name) if that nickname is bad -- and a
    GUID already present is never overwritten by a later live nickname, so a
    manual fix sticks across future runs.
    """
    if guid and guid in owners_map:
        return owners_map[guid]
    if nickname:
        if guid:
            owners_map[guid] = nickname
        return nickname
    if team_name in legacy_owner_map:
        return legacy_owner_map[team_name]
    warnings.warn(f"No owner resolvable for team_name: {team_name!r}")
    return team_name


@lru_cache(maxsize=None)
def to_league(gm: yfa.Game, lkey: str) -> yfa.League:
    return gm.to_league(lkey)


@CACHE.cache(ignore=["gm"])
def fetch_manager_data(gm: yfa.Game, lkey: str) -> Dict[str, Dict[str, str]]:
    """Manager GUID + nickname per team_key, for stable owner identity across years."""
    lg = to_league(gm, lkey)
    manager_map = {}
    for team_key, team_data in lg.teams().items():
        managers = team_data.get("managers") or []
        if managers:
            manager = managers[0]["manager"]
            manager_map[team_key] = {
                "guid": manager.get("guid", ""),
                "nickname": manager.get("nickname", team_data.get("name", "")),
            }
    return manager_map


@CACHE.cache(ignore=["gm"])
def fetch_standings(gm: yfa.Game, lkey: str) -> List[dict]:
    return to_league(gm, lkey).standings()


@CACHE.cache(ignore=["gm"])
def fetch_draft(gm: yfa.Game, lkey: str) -> List[dict]:
    return to_league(gm, lkey).draft_results()


@CACHE.cache(ignore=["gm"])
def fetch_transactions(gm: yfa.Game, lkey: str) -> List[dict]:
    return to_league(gm, lkey).transactions(TRANSACTION_TYPES, "")


@CACHE.cache(ignore=["gm"])
def fetch_matchups_raw(gm: yfa.Game, lkey: str, week: int) -> dict:
    return to_league(gm, lkey).matchups(week)


@CACHE.cache(ignore=["gm"])
def fetch_roster(gm: yfa.Game, lkey: str, team_key: str, week: int) -> List[dict]:
    return to_league(gm, lkey).to_team(team_key).roster(week=week)


def _parse_matchup_teams(raw_scoreboard: dict) -> List[List[dict]]:
    """Flatten Yahoo's raw scoreboard JSON into one list of teams per matchup.

    Each team entry in the raw JSON is `[[<metadata dicts...>], {"team_points":
    {...}}, {"team_projected_points": {...}}]` -- index 0 holds name/team_key/
    managers/etc (the same shape yahoo_fantasy_api's own League.standings()
    pulls from), and the actual score lives in the sibling "team_points" dict,
    not inside that metadata list.
    """
    t = objectpath.Tree(raw_scoreboard)
    try:
        count = int(next(iter(t.execute("$..matchups.count"))))
    except StopIteration:
        return []

    matchups = []
    for i in range(count):
        teams = []
        for team_arr in t.execute('$..matchups.."{}".matchup..teams..team'.format(i)):
            team: dict = {}
            score = None
            for part in team_arr:
                if isinstance(part, list):
                    for field in part:
                        if isinstance(field, dict):
                            team.update(field)
                elif isinstance(part, dict):
                    if "team_points" in part:
                        score = part["team_points"].get("total")
                    else:
                        team.update(part)
            team["score"] = score
            teams.append(team)
        matchups.append(teams)
    return matchups


def scrape_league_season(
    gm: yfa.Game,
    lkey: str,
    season: int,
    owners_map: Dict[str, str],
    legacy_owner_map: Dict[str, str],
) -> Dict[str, pd.DataFrame]:
    """Pull standings/draft/managers/matchups/transactions/rosters for a single league-season.

    `owners_map` (guid -> display_name) is mutated in place as new managers
    are discovered -- callers should persist it once after the full scrape.
    """
    lg = to_league(gm, lkey)

    manager_map = fetch_manager_data(gm, lkey)

    standings_raw = fetch_standings(gm, lkey)
    standings_df = pd.DataFrame(standings_raw)
    if standings_df.empty:
        logger.warning("No standings returned for %s season %s", lkey, season)
        return {}

    tn_col = "name" if "name" in standings_df.columns else "team_name"
    standings_df["owner"] = standings_df.apply(
        lambda row: resolve_owner(
            manager_map.get(row["team_key"], {}).get("guid"),
            manager_map.get(row["team_key"], {}).get("nickname"),
            row[tn_col],
            owners_map,
            legacy_owner_map,
        ),
        axis=1,
    )
    standings_df["manager_guid"] = standings_df["team_key"].map(lambda k: manager_map.get(k, {}).get("guid", ""))
    standings_df["season"] = season

    tk_owner = dict(zip(standings_df["team_key"], standings_df["owner"]))
    tk_guid = dict(zip(standings_df["team_key"], standings_df["manager_guid"]))
    tk_name = dict(zip(standings_df["team_key"], standings_df[tn_col]))

    draft_df = pd.DataFrame(fetch_draft(gm, lkey))
    if not draft_df.empty:
        draft_df["owner"] = draft_df["team_key"].map(tk_owner)
        draft_df["manager_guid"] = draft_df["team_key"].map(tk_guid)
        draft_df["season"] = season

    trans_df = pd.DataFrame(fetch_transactions(gm, lkey))
    if not trans_df.empty:
        key_col = next(
            (c for c in ("team_key", "trader_team_key", "destination_team_key") if c in trans_df.columns),
            None,
        )
        if key_col:
            trans_df["owner"] = trans_df[key_col].map(tk_owner)
            trans_df["manager_guid"] = trans_df[key_col].map(tk_guid)
        else:
            warnings.warn(f"No team-key column found in transactions for {lkey} {season}")
            trans_df["owner"] = ""
            trans_df["manager_guid"] = ""
        trans_df["season"] = season

    managers_df = pd.DataFrame(
        [
            {"team_key": k, "manager_guid": v["guid"], "nickname": v["nickname"], "season": season}
            for k, v in manager_map.items()
        ]
    )

    matchup_rows: List[dict] = []
    roster_rows: List[dict] = []
    end_week = lg.end_week()
    for wk in range(1, end_week + 1):
        raw = fetch_matchups_raw(gm, lkey, wk)
        week_matchups = _parse_matchup_teams(raw)
        if not week_matchups:
            logger.warning("No matchups parsed for %s season %s week %s", lkey, season, wk)
        for matchup in week_matchups:
            for team in matchup:
                team_key = team.get("team_key", "")
                score = team.get("score")
                matchup_rows.append(
                    {
                        "season": season,
                        "week": wk,
                        "team_key": team_key,
                        "team_name": tk_name.get(team_key, team.get("name", "")),
                        "owner": tk_owner.get(team_key, ""),
                        "manager_guid": tk_guid.get(team_key, ""),
                        "score": float(score) if score not in (None, "") else 0.0,
                    }
                )

        for team_key in standings_df["team_key"]:
            roster = fetch_roster(gm, lkey, team_key, wk)
            for plyr in roster:
                roster_rows.append(
                    {
                        "season": season,
                        "week": wk,
                        "team_key": team_key,
                        "owner": tk_owner.get(team_key, ""),
                        "manager_guid": tk_guid.get(team_key, ""),
                        **plyr,
                    }
                )

    return {
        "standings": standings_df,
        "draft": draft_df,
        "managers": managers_df,
        "matchups": pd.DataFrame(matchup_rows),
        "transactions": trans_df,
        "rosters": pd.DataFrame(roster_rows),
    }
