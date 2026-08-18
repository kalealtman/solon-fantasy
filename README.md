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

By default this scrapes 2014 through the current year. Override with `--start-year` / `--end-year`. Output:

- `data/raw/.joblib_cache/` -- per-call cache (gitignored). Lets an interrupted run resume without re-pulling everything.
- `data/processed/*.csv` -- consolidated, committed output: `standings.csv`, `draft.csv`, `managers.csv`, `matchups.csv`, `transactions.csv`, `rosters.csv`.

## Config

- `config/league_ids.txt` -- Yahoo league IDs (one per year the league existed) that belong to this league.
- `config/owner_map.csv` -- fallback team-name -> owner mapping, used when a season's manager data doesn't carry a nickname.