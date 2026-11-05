"""Build a Google Ads API client from environment variables.

Credentials come from the process environment or from a local ``.env.googleads``
file in the repository root (git-ignored). Nothing secret is ever written by
these scripts.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env.googleads"
LOG_FILE = ROOT / ".claude" / "google-ads" / "changes.jsonl"

REQUIRED = (
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GOOGLE_ADS_CUSTOMER_ID",
)


def load_env_file(path: Path = ENV_FILE) -> None:
    """Load KEY=VALUE lines into os.environ without overriding real env vars."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def customer_id() -> str:
    load_env_file()
    cid = digits(os.environ.get("GOOGLE_ADS_CUSTOMER_ID", ""))
    if not cid:
        sys.exit("GOOGLE_ADS_CUSTOMER_ID is not set (see googleads/README.md).")
    return cid


def get_client():
    """Return a GoogleAdsClient or exit with a clear message if not configured."""
    load_env_file()
    missing = [k for k in REQUIRED if not os.environ.get(k)]
    if missing:
        sys.exit(
            "Missing Google Ads settings: "
            + ", ".join(missing)
            + "\nFill them in .env.googleads (see googleads/README.md)."
        )
    from google.ads.googleads.client import GoogleAdsClient

    config = {
        "developer_token": os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": os.environ["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        "use_proto_plus": True,
    }
    login = digits(os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", ""))
    if login:
        config["login_customer_id"] = login
    return GoogleAdsClient.load_from_dict(config)


def query(client, gaql: str, cid: str | None = None):
    """Run a GAQL query and yield rows."""
    service = client.get_service("GoogleAdsService")
    for row in service.search(customer_id=cid or customer_id(), query=gaql):
        yield row


def money(micros: int) -> float:
    return round(micros / 1_000_000, 2)
