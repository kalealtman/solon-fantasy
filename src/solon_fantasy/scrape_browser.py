"""Browser-scraping stopgap while Yahoo Fantasy Sports API access is
pending (see the API-based scrape.py / league_discovery.py for the real
version this is meant to be replaced by once access clears).

These are pure parsing functions over already-fetched HTML strings -- kept
separate from the Playwright navigation code in scripts/run_scrape_browser.py
so they can be tested directly against saved sample pages.
"""
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup

BASE_URL = "https://football.fantasysports.yahoo.com"


def _team_id_from_href(href: Optional[str]) -> str:
    if not href:
        return ""
    m = re.search(r"/f1/\d+/(\d+)\b", href) or re.search(r"^/\d+/f1/\d+/(\d+)\b", href)
    return m.group(1) if m else ""


def _player_id_from_href(href: Optional[str]) -> str:
    if not href:
        return ""
    m = re.search(r"/players/(\d+)", href)
    return m.group(1) if m else ""


def resolve_league_id(html: str) -> Optional[str]:
    """Pull the numeric league_id out of any page for a given season (it's
    embedded in the season-switcher form action and in every team link)."""
    m = re.search(r'/f1/(\d+)/gotoseason', html) or re.search(r'/f1/(\d+)/', html)
    return m.group(1) if m else None


def parse_seasons(html: str) -> List[int]:
    """Every season this league has existed under its current slug, from the
    season-switcher dropdown. Does NOT necessarily include the league's
    first-ever year if it was a freshly-created league that season (no prior
    season to link back to) -- same caveat as the API version's renew chain."""
    soup = BeautifulSoup(html, "html.parser")
    select = soup.find("select", id="seasonspec")
    if not select:
        return []
    seasons = []
    for opt in select.find_all("option"):
        m = re.match(r"(\d{4})_", opt.get("value", ""))
        if m:
            seasons.append(int(m.group(1)))
    return sorted(seasons)


def parse_standings(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="standingstable")
    if not table:
        return []
    rows = []
    for tr in table.find("tbody").find_all("tr"):
        cells = tr.find_all("td")
        # Each row has two links matching this href pattern: a logo-only one
        # and the text-bearing team name -- take whichever one has text.
        team_link = next(
            (a for a in tr.find_all("a", href=re.compile(r"/f1/\d+/\d+$")) if a.get_text(strip=True)),
            None,
        )
        wlt = cells[2].get_text(strip=True)
        wins, losses, ties = (wlt.split("-") + ["0"])[:3]
        rows.append(
            {
                "rank": re.sub(r"\D", "", cells[0].get_text(strip=True)),
                "team_id": _team_id_from_href(team_link["href"] if team_link else None),
                "team_name": team_link.get_text(strip=True) if team_link else "",
                "wins": int(wins),
                "losses": int(losses),
                "ties": int(ties or 0),
                "points_for": float(cells[3].get_text(strip=True) or 0),
                "points_against": float(cells[4].get_text(strip=True) or 0),
                "streak": cells[5].get_text(strip=True),
                "waiver_budget": cells[6].get_text(strip=True) if len(cells) > 6 else "",
                "waiver_priority": cells[7].get_text(strip=True) if len(cells) > 7 else "",
                "moves": cells[8].get_text(strip=True) if len(cells) > 8 else "",
            }
        )
    return rows


def parse_draft(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    picks = []
    overall = 0
    for table in soup.select("table.Table"):
        header = table.find("th")
        if not header or not re.match(r"Round\s+\d+", header.get_text(strip=True)):
            continue
        round_num = int(re.search(r"\d+", header.get_text()).group())
        for tr in table.find("tbody").find_all("tr"):
            overall += 1
            pick_in_round = tr.find("td", class_="first")
            player_link = tr.find("a", class_="name")
            team_cell = tr.find("td", class_="last")
            picks.append(
                {
                    "round": round_num,
                    "pick": int(re.sub(r"\D", "", pick_in_round.get_text())) if pick_in_round else None,
                    "overall_pick": overall,
                    "player_name": player_link.get_text(strip=True) if player_link else "",
                    "player_id": _player_id_from_href(player_link["href"] if player_link else None),
                    "team_name": team_cell.get("title", team_cell.get_text(strip=True)) if team_cell else "",
                }
            )
    return picks


def parse_matchups(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for li in soup.select("li[data-target*='matchup?week=']"):
        m = re.search(r"week=(\d+)&(?:amp;)?mid1=(\d+)&(?:amp;)?mid2=(\d+)", li.get("data-target", ""))
        if not m:
            continue
        week = int(m.group(1))
        team_links = li.select("a.F-link")
        score_blocks = li.select("div.Fz-lg")
        if len(team_links) != 2 or len(score_blocks) != 2:
            continue
        for team_link, score_block in zip(team_links, score_blocks):
            rows.append(
                {
                    "week": week,
                    "team_id": _team_id_from_href(team_link.get("href")),
                    "team_name": team_link.get_text(strip=True),
                    "score": float(score_block.get_text(strip=True) or 0),
                }
            )
    return rows


def parse_transactions(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_=re.compile("Tst-transaction-table"))
    if not table:
        return []
    rows = []
    for tr in table.find("tbody").find_all("tr", recursive=False):
        icon_cell, detail_cell, team_cell = tr.find_all("td")[:3]
        actions = [span.get("title", "") for span in icon_cell.find_all("span", class_="F-icon")]
        blocks = detail_cell.find_all("div", class_="Pbot-xs")
        team_link = team_cell.find("a", class_="Tst-team-name")
        timestamp = team_cell.find("span", class_="F-timestamp")
        for action, block in zip(actions, blocks):
            name_link = block.find("a")
            note = block.find("h6")
            rows.append(
                {
                    "action": "add" if "Added" in action else "drop",
                    "player_name": name_link.get_text(strip=True) if name_link else "",
                    "player_id": _player_id_from_href(name_link.get("href") if name_link else None),
                    "note": note.get_text(strip=True) if note else "",
                    "team_id": _team_id_from_href(team_link.get("href") if team_link else None),
                    "team_name": team_link.get_text(strip=True) if team_link else "",
                    "timestamp": timestamp.get_text(strip=True) if timestamp else "",
                }
            )
    return rows


def parse_trades(html: str) -> List[dict]:
    """Trades render very differently from add/drop rows in the same table:
    each trade is TWO <tr> (one per side, linked by rowspan="2" on the status
    icon cell), and Yahoo lists vetoed/rejected proposals right alongside
    completed ones -- only rows whose icon is specifically "F-trade" (not
    e.g. "F-negative" for vetoed) represent a trade that actually happened.
    Returns one row per side (two per trade, sharing the same trade_id), so
    counting "trades per owner" is a simple groupby, same as adds/drops.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_=re.compile("Tst-transaction-table"))
    if not table:
        return []
    all_rows = table.find("tbody").find_all("tr", recursive=False)

    rows = []
    trade_id = 0
    i = 0
    while i < len(all_rows):
        icon_cell = all_rows[i].find("td", attrs={"rowspan": True})
        if icon_cell is None or i + 1 >= len(all_rows):
            i += 1  # not a trade pair (unexpected shape) -- skip defensively
            continue
        icon = icon_cell.find("span", class_="F-icon")
        completed = bool(icon and "F-trade" in icon.get("class", []))
        trade_id += 1

        for side_row in (all_rows[i], all_rows[i + 1]):
            players_cell = side_row.find("td", class_="No-pstart")
            note_cell = side_row.find("td", class_="Fz-xxs")
            team_cell = side_row.find("td", class_="Ta-end")
            team_link = next(
                (a for a in (team_cell.find_all("a", href=re.compile(r"/f1/\d+/\d+$")) if team_cell else []) if a.get_text(strip=True)),
                None,
            )
            timestamp = team_cell.find("span", class_="F-timestamp") if team_cell else None
            players = [p.find("a").get_text(strip=True) for p in (players_cell.find_all("p") if players_cell else []) if p.find("a")]
            rows.append(
                {
                    "trade_id": trade_id,
                    "completed": completed,
                    "note": note_cell.get_text(strip=True) if note_cell else "",
                    "team_id": _team_id_from_href(team_link.get("href")) if team_link else "",
                    "team_name": team_link.get_text(strip=True) if team_link else "",
                    "players_received": "; ".join(players),
                    "timestamp": timestamp.get_text(strip=True) if timestamp else "",
                }
            )
        i += 2
    return rows


def has_next_transactions_page(html: str) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    next_link = soup.find("a", string=re.compile(r"Next\s+25"))
    return bool(next_link and next_link.get("href"))


def parse_roster(html: str) -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table in soup.select("table[id^='statTable']"):
        for tr in table.find("tbody").find_all("tr"):
            pos_span = tr.find("span", class_="pos-label")
            name_link = tr.find("a", class_="name")
            if not name_link:
                continue
            rows.append(
                {
                    "selected_position": pos_span.get("data-pos", "") if pos_span else "",
                    "player_name": name_link.get_text(strip=True),
                    "player_id": _player_id_from_href(name_link.get("href")),
                }
            )
    return rows
