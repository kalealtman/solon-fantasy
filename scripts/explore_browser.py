#!/usr/bin/env python
"""Interactive helper: opens a real browser window with a persistent login
profile, so you can navigate Yahoo Fantasy's pages by hand and snapshot
whichever one is currently loaded. This is step 1 of the browser-scraping
stopgap (while Yahoo Fantasy Sports API access is still pending) -- it lets
the real page structure get inspected before any parser gets written against
it, instead of guessing at HTML selectors blind.

Usage:
    python scripts/explore_browser.py

First run: log into Yahoo in the window that opens. The session is cached in
the local, gitignored .browser_profile/ folder, so you only log in once.

Then, for each page you want captured: click around Yahoo's site normally to
get to it, switch back to this terminal, type a short label, and hit Enter.
Saved to data/raw/exploration/<n>_<label>.html (+ a screenshot). Type 'quit'
to stop.
"""
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILE_DIR = REPO_ROOT / ".browser_profile"
OUT_DIR = REPO_ROOT / "data" / "raw" / "exploration"


def slugify(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "page"


def snapshot(page) -> str:
    """Grab the current page's HTML, tolerating Yahoo's heavy ad/tracker
    load and any in-flight client-side navigation at the moment of capture."""
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10000)
    except Exception:
        pass
    last_err = None
    for _ in range(3):
        try:
            return page.content()
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise last_err


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE_DIR), headless=False)
        page = context.pages[0] if context.pages else context.new_page()
        try:
            # domcontentloaded (not the default "load") so this doesn't wait
            # on every ad/tracker on the page to finish.
            page.goto("https://football.fantasysports.yahoo.com/", wait_until="domcontentloaded", timeout=60000)
        except Exception:
            print("(initial page load was slow/timed out -- that's fine, just navigate manually below)")

        print("Log into Yahoo in the browser window if it asks (one time only).")
        print("Navigate to a page you want captured, then come back here.")
        print("Type a short label (e.g. 'standings_2024') and hit Enter to snapshot it.")
        print("Type 'quit' to stop.\n")

        n = 0
        while True:
            label = input("Label for current page (or 'quit'): ").strip()
            if label.lower() in ("quit", "q", "exit", ""):
                break
            try:
                html = snapshot(page)
            except Exception as e:
                print(f"  couldn't capture that page ({e}); try the label again")
                continue
            n += 1
            slug = f"{n:02d}_{slugify(label)}"
            (OUT_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
            try:
                page.screenshot(path=str(OUT_DIR / f"{slug}.png"), full_page=True)
            except Exception:
                pass  # nice-to-have, not essential
            print(f"  saved {slug} (url: {page.url})")

        context.close()


if __name__ == "__main__":
    main()
