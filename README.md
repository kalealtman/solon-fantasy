# solon-fantasy

Historical data for the Solon fantasy football league (Yahoo, running since 2014): standings, draft results, managers, weekly matchups, transactions, and weekly rosters.

This phase is data-pull only. Analysis/presentation is a later phase.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env` with your Yahoo Developer App credentials (from https://developer.yahoo.com/apps/ -- reuse an existing app if you have one).

## Running the scrape

```
python scripts/run_scrape.py
```

First run opens a browser for Yahoo's OAuth flow -- log in, paste the verifier code back into the terminal. The resulting token is cached to a local `oauth2.json` (gitignored) and refreshed automatically afterward.

Every season the league exists on Yahoo is discovered automatically (see [Config](#config) below) -- no yearly editing required. Restrict the range with `--start-year` / `--end-year` if you just want to test against one season. Output:

- `data/raw/.joblib_cache/` -- per-call cache (gitignored). Lets an interrupted run resume without re-pulling everything.
- `data/processed/*.csv` -- consolidated, committed output: `standings.csv`, `draft.csv`, `managers.csv`, `matchups.csv`, `transactions.csv`, `rosters.csv`.

## Config

- `config/owners.csv` -- **self-populating**, `manager_guid -> display_name`. The scraper adds a new row the first time it sees a GUID it doesn't recognize (using whatever nickname Yahoo gives it), and never overwrites a GUID that's already there -- so hand-editing a display name here sticks for good. This is the source of truth for "who owns this team," since a GUID is stable per person even when they rename their team every year.
- `config/owner_map.csv` -- legacy fallback, `team_name -> owner`, only consulted for the rare case where a season has no manager GUID or nickname at all.
- `config/league_id_overrides.txt` -- manual `season=league_key` entries for seasons the renew-chain walk can't reach on its own (see below). Empty by default.

### How seasons are found

`src/solon_fantasy/league_discovery.py` finds the most recent season whose league name matches `--league-name` (default `"Solon"`), then walks Yahoo's `renew` field backward season by season to reconstruct the full history -- Yahoo links each renewed league to the league it was renewed from. A brand-new season is picked up automatically the moment it exists on Yahoo; nothing to edit.

This can't reach a season with no `renew` link back to it -- most likely the league's first-ever year (2014 here, if it turns out to have been created fresh rather than renewed). Add those manually to `config/league_id_overrides.txt`.

### Reusing this for another league

Point `--league-name` at a substring of your league's name and it should work as-is, no code changes -- that's the whole point of the auto-discovery + self-populating owners map. `config/owner_map.csv` and `config/league_id_overrides.txt` can both start empty.