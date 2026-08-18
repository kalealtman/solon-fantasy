"""Builds an authenticated Yahoo OAuth2 session.

Consumer key/secret come from environment variables (via .env, gitignored).
The access/refresh token is cached to a local, gitignored oauth2.json and
refreshed automatically when it expires. yahoo_oauth's OAuth2(from_file=...)
reads consumer_key/consumer_secret/tokens straight out of that json file, so
on first run (no oauth2.json yet) we seed the file with just the consumer
key/secret from the environment -- that's enough for yahoo_oauth to detect
there's no token yet and kick off its interactive browser OAuth flow, after
which it writes the full credential set (including the token) back to the
same file.
"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from yahoo_oauth import OAuth2

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TOKEN_FILE = REPO_ROOT / "oauth2.json"


def get_session(token_file: Path = DEFAULT_TOKEN_FILE) -> OAuth2:
    """Return a valid, auto-refreshed OAuth2 session."""
    load_dotenv(REPO_ROOT / ".env")

    if not token_file.exists():
        consumer_key = os.environ.get("YAHOO_CONSUMER_KEY")
        consumer_secret = os.environ.get("YAHOO_CONSUMER_SECRET")
        if not consumer_key or not consumer_secret:
            raise RuntimeError(
                "YAHOO_CONSUMER_KEY / YAHOO_CONSUMER_SECRET must be set in .env "
                f"(copy .env.example) before first run -- no token cached at {token_file}"
            )
        token_file.write_text(
            json.dumps({"consumer_key": consumer_key, "consumer_secret": consumer_secret}),
            encoding="utf-8",
        )

    session = OAuth2(None, None, from_file=str(token_file))
    if not session.token_is_valid():
        session.refresh_access_token()
    return session
