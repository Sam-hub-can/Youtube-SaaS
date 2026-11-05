"""Build the weekly summary and send it to the Jarvis webhook.

Usage:
    python -m googleads.summary --dry-run     # print the payload, send nothing
    python -m googleads.summary               # build from the live account and POST it

Settings (in .env.googleads, never committed):
    JARVIS_WEBHOOK_URL      required to send
    JARVIS_WEBHOOK_SECRET   optional; if set, the body is signed with HMAC-SHA256
                            and sent in the X-Signature header as "sha256=<hex>"
    JARVIS_APP / JARVIS_PANEL   default "chattervane" / "app-data"
"""
import argparse
import hmac
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from googleads.client import LOG_FILE, load_env_file


def recent_changes(days: int = 7):
    if not LOG_FILE.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    out = []
    for line in LOG_FILE.read_text().splitlines():
        try:
            e = json.loads(line)
            if datetime.fromisoformat(e["time"]) >= cutoff:
                out.append(e)
        except (ValueError, KeyError):
            continue
    return out


def build_summary(data: dict, changes: list, safe_types: set) -> dict:
    camps = data["campaigns"]
    cost = round(sum(c["cost"] for c in camps), 2)
    conv = round(sum(c["conversions"] for c in camps), 2)
    clicks = sum(c["clicks"] for c in camps)
    impressions = sum(c["impressions"] for c in camps)
    alerts = []
    for c in camps:
        if c["lost_is_budget"] >= 20:
            alerts.append(f"{c['name']}: losing {c['lost_is_budget']}% of impressions to budget")
        if c["cost"] > 0 and c["conversions"] == 0:
            alerts.append(f"{c['name']}: spent {c['cost']} with no conversions")
    if data["disapproved_ads"]:
        alerts.append(f"{len(data['disapproved_ads'])} disapproved ad(s)")
    return {
        "source": "google-ads-operator",
        "app": os.environ.get("JARVIS_APP", "chattervane"),
        "panel": os.environ.get("JARVIS_PANEL", "app-data"),
        "title": "Google Ads weekly review",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "period_days": data["days"],
        "totals": {
            "cost": cost, "clicks": clicks, "impressions": impressions,
            "ctr": round(clicks / impressions * 100, 2) if impressions else 0,
            "conversions": conv,
            "cpa": round(cost / conv, 2) if conv else None,
        },
        "campaigns": [
            {k: c[k] for k in ("name", "status", "daily_budget", "cost", "clicks",
                               "conversions", "cpa", "roas", "lost_is_budget")}
            for c in camps[:10]
        ],
        "wasted_search_terms": data["wasted_search_terms"][:10],
        "changes_made": [{k: v for k, v in e.items() if k != "result"} for e in changes],
        "needs_approval": [
            {"type": r["type"], "campaign": r["campaign"]}
            for r in data["recommendations"] if r["type"] not in safe_types
        ],
        "alerts": alerts,
    }


def post(payload: dict) -> None:
    url = os.environ.get("JARVIS_WEBHOOK_URL")
    if not url:
        sys.exit("JARVIS_WEBHOOK_URL is not set (see googleads/README.md).")
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "User-Agent": "google-ads-operator"}
    secret = os.environ.get("JARVIS_WEBHOOK_SECRET")
    if secret:
        headers["X-Signature"] = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"Sent to Jarvis: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        sys.exit(f"Jarvis rejected the summary: HTTP {e.code} {e.reason}")
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach Jarvis: {e.reason}")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--dry-run", action="store_true", help="print the payload, send nothing")
    a = p.parse_args()
    load_env_file()
    from googleads import report
    from googleads.actions import SAFE_RECOMMENDATIONS

    payload = build_summary(report.build(a.days), recent_changes(a.days), SAFE_RECOMMENDATIONS)
    if a.dry_run:
        print(json.dumps(payload, indent=2, default=str))
    else:
        post(payload)


if __name__ == "__main__":
    main()
