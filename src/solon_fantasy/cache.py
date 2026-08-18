"""Resumable on-disk cache for Yahoo API calls.

Caching at the function level (rather than just writing final CSVs) means an
interrupted scrape can be re-run and will skip any league-season/week/team
call it already completed.
"""
from pathlib import Path

from joblib import Memory

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "raw" / ".joblib_cache"
CACHE = Memory(CACHE_DIR, verbose=0)
