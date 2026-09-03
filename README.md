# Solon Fantasy Football

Historical data and an interactive site for the Solon fantasy football league (Yahoo, running since 2014): standings, drafts, matchups, transactions, trades, and derived records.

**Live site:** https://kalealtman.github.io/solon-fantasy/

## How it fits together

```
scrape (Playwright)  -->  data/processed/*.csv  -->  build_derived_stats.py  -->  build_site.py  -->  site/dist/solon_site.html
                                                                                          |
                                                                                   GitHub Actions
                                                                                          |
                                                                                   GitHub Pages
```

Yahoo's official Fantasy Sports API now requires a gated developer-access application with no fixed turnaround, so data collection goes through browser automation against the normal Yahoo Fantasy web pages instead.

## Data pipeline

- `scripts/run_scrape_browser.py` -- drives a real (Playwright-controlled) browser against Yahoo's fantasy pages: standings, draft results, matchups/scoreboard, transactions, trades, rosters. First run opens a visible browser window for a one-time interactive Yahoo login; the session is cached in `.browser_profile/` (gitignored) so later runs don't need to log in again. Fetched pages are cached under `data/raw/browser_cache/` (gitignored) so an interrupted run can resume without re-hitting Yahoo.
  - `--start-year` / `--end-year` to restrict the season range (e.g. to pull just a newly-finished season)
  - `--skip-rosters` to skip the slow team x week roster pull
- `scripts/backfill_trades.py`, `scripts/append_2014.py`, `scripts/reparse_standings.py` -- one-off scripts used to backfill or repair specific gaps found after the fact; not part of the normal yearly run.
- `scripts/clean_data.py` -- normalizes inconsistent curly-quote/apostrophe text across `data/processed/*.csv` (Yahoo renders the same name differently on different pages).
- `scripts/build_derived_stats.py` -- computes everything that isn't a direct scrape: career totals per owner, head-to-head records, and the record book (`data/processed/owner_career.csv`, `head_to_head.csv`, `trophy_case.csv`).
- `data/processed/*.csv` -- the committed, canonical data: `standings`, `draft`, `matchups`, `transactions`, `trades`, `owner_career`, `head_to_head`, `trophy_case`, `rosters`. Everything here is derived from `data/raw/` and safe to regenerate.

### Config

- `config/owner_map.csv` -- `team_name -> owner`. Team names change yearly; this is the join key used everywhere to track a human owner across seasons (Yahoo's browser pages don't expose a stable manager ID the way the official API does).
- `config/league_id_overrides.txt` -- manual `season=league_key` entries for any season the scraper can't resolve automatically.

## The site

`site/template.html` (page shell/CSS) + `site/app.js` (all client logic) + a JSON export of `data/processed/*.csv` are combined into one self-contained HTML file by:

```
python scripts/build_site.py
```

This writes `site/dist/solon_site.html` (gitignored -- it's just the inputs above baked together, and goes stale the moment any of them changes). Open it directly in a browser to preview locally.

### Deployment

`.github/workflows/deploy-site.yml` runs `build_site.py` and publishes the output to **GitHub Pages** automatically on every push to `main` that touches `site/`, `data/processed/`, `config/`, or the build script itself. No manual publish step -- push the data/code change and the live site updates in a minute or two.

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
playwright install
```

## Running a fresh pull (new season, or re-scraping)

```
python scripts/run_scrape_browser.py --start-year 2026 --end-year 2026
python scripts/clean_data.py
python scripts/build_derived_stats.py
python scripts/build_site.py
```

Commit the updated `data/processed/*.csv` -- the Pages deploy picks up from there.
