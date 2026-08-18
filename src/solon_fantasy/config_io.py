"""Reads and writes the small config files under config/.

Two kinds of file here:
  - hand-maintained: owner_map.csv (legacy team-name fallback), league_id_overrides.txt
  - self-populating: owners.csv, which the scraper grows on its own as it
    discovers new manager GUIDs, and which a human can hand-edit afterward to
    fix a display name -- edits stick, since a GUID already in the file is
    never overwritten by a live Yahoo nickname.
"""
import csv
from pathlib import Path
from typing import Dict


def load_owner_map(path: Path) -> Dict[str, str]:
    """Legacy team_name -> owner fallback, for seasons where Yahoo manager
    data is missing entirely (no guid, no nickname)."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["team_name"].strip(): row["owner"].strip() for row in csv.DictReader(f)}


def load_owners_map(path: Path) -> Dict[str, str]:
    """Self-populating manager_guid -> display_name map."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8") as f:
        return {row["guid"]: row["display_name"] for row in csv.DictReader(f) if row.get("guid")}


def save_owners_map(path: Path, owners: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["guid", "display_name"])
        for guid, name in sorted(owners.items(), key=lambda kv: kv[1].lower()):
            writer.writerow([guid, name])


def load_league_overrides(path: Path) -> Dict[int, str]:
    """Optional manual season -> league_key entries, for seasons the renew
    chain can't reach on its own (e.g. the league's first-ever season, which
    has no prior season to link back to). Format: one `season=league_key`
    per line, '#' comments allowed."""
    if not path.exists():
        return {}
    overrides = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            season, lkey = line.split("=", 1)
            overrides[int(season.strip())] = lkey.strip()
    return overrides
