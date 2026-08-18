"""Auto-discovers every league-season by walking Yahoo's `renew` chain,
instead of hand-maintaining a list of league IDs.

Yahoo links a renewed league to the season it was renewed from via a `renew`
field on league settings (format: "<game_id>_<league_id>"). So starting from
just one known season -- found by matching the league name -- we can walk
backward and reconstruct the full history, with zero config changes needed
when a new season shows up on Yahoo each year.

The chain necessarily stops at whatever season the league was first created
in Yahoo (no prior season to link back to). If the league was ever recreated
from scratch mid-history (a new league rather than a renewal), the chain will
stop there too -- config/league_id_overrides.txt exists to bridge exactly
that gap.
"""
import logging
from datetime import date
from typing import Dict, Optional

import yahoo_fantasy_api as yfa

from .scrape import to_league

logger = logging.getLogger(__name__)


def _find_league_by_name(gm: yfa.Game, name_match: str, year: int) -> Optional[str]:
    matched = None
    for lkey in gm.league_ids(year=year) or []:
        name = to_league(gm, lkey).settings().get("name", "")
        if name_match.lower() in name.lower():
            if matched is not None:
                raise RuntimeError(
                    f"Multiple leagues matching {name_match!r} found for {year}: {matched}, {lkey}. "
                    "Use a more specific --league-name to disambiguate."
                )
            matched = lkey
    return matched


def find_latest_league_key(gm: yfa.Game, name_match: str, search_years: int = 2) -> str:
    """Find the most recent season's league key by name match, stepping
    backward a year at a time in case the current season hasn't been
    renewed on Yahoo yet."""
    this_year = date.today().year
    for year in range(this_year, this_year - search_years, -1):
        lkey = _find_league_by_name(gm, name_match, year)
        if lkey:
            return lkey
    raise RuntimeError(
        f"No league matching {name_match!r} found for {this_year - search_years + 1}-{this_year}"
    )


def discover_league_chain(gm: yfa.Game, name_match: str) -> Dict[int, str]:
    """Return {season_year: league_key} for every connected season, walking
    Yahoo's renew chain backward from the most recent season found."""
    lkey = find_latest_league_key(gm, name_match)
    chain: Dict[int, str] = {}
    while lkey:
        settings = to_league(gm, lkey).settings()
        season = int(settings["season"])
        if season in chain:
            logger.warning("renew chain looped back to season %s (%s) -- stopping", season, lkey)
            break
        chain[season] = lkey
        renew = (settings.get("renew") or "").strip()
        if not renew or "_" not in renew:
            break
        game_id, prev_league_id = renew.split("_", 1)
        lkey = f"{game_id}.l.{prev_league_id}"
    return chain
