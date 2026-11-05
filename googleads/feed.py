"""Write the campaign status feed that the Jarvis dashboard panel reads.

Run it every time you check the campaign (the panel warns if as_of is over 36 h old):
    python -m googleads.feed             # write the feed file
    python -m googleads.feed --dry-run   # print the entry, write nothing

Settings (.env.googleads):
    JARVIS_FEED_PATH          default /home/sam/Projects/Jarvis/chattervane-ads-feed.json
    JARVIS_FEED_KEY           default google-app
    JARVIS_FEED_CAMPAIGN_IDS  comma-separated campaign ids; empty = all App campaigns

Figures are lifetime totals since the campaign started. Spend is in CA$; if the
account currency is not CAD, spend is left out and the note says why.
Fields that are unknown are left out. Other campaigns already in the file are kept.
"""
import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from googleads.client import get_client, load_env_file, money, query

DEFAULT_PATH = "/home/sam/Projects/Jarvis/chattervane-ads-feed.json"
STRENGTH_ORDER = ["POOR", "AVERAGE", "GOOD", "EXCELLENT"]


def _ids():
    raw = os.environ.get("JARVIS_FEED_CAMPAIGN_IDS", "")
    return [x.strip() for x in raw.split(",") if x.strip().isdigit()]


def fetch(client):
    ids = _ids()
    where = f"campaign.id IN ({', '.join(ids)})" if ids else "campaign.advertising_channel_type = 'MULTI_CHANNEL'"
    where += " AND campaign.status != 'REMOVED'"
    camps = [{
        "name": r.campaign.name, "status": r.campaign.status.name,
        "start": r.campaign.start_date_time, "end": r.campaign.end_date_time,
        "cost": money(r.metrics.cost_micros), "impressions": r.metrics.impressions,
        "clicks": r.metrics.clicks,
    } for r in query(client, f"""
        SELECT campaign.id, campaign.name, campaign.status, campaign.start_date_time,
               campaign.end_date_time, metrics.cost_micros, metrics.impressions, metrics.clicks
        FROM campaign WHERE {where}""")]
    installs = None
    rows = list(query(client, f"""
        SELECT metrics.conversions FROM campaign
        WHERE {where} AND segments.conversion_action_category = 'DOWNLOAD'"""))
    if rows:
        installs = int(round(sum(r.metrics.conversions for r in rows)))
    ads = [{
        "strength": r.ad_group_ad.ad_strength.name,
        "approval": r.ad_group_ad.policy_summary.approval_status.name,
        "review": r.ad_group_ad.policy_summary.review_status.name,
        "status": r.ad_group_ad.status.name,
    } for r in query(client, f"""
        SELECT ad_group_ad.ad_strength, ad_group_ad.status,
               ad_group_ad.policy_summary.approval_status, ad_group_ad.policy_summary.review_status
        FROM ad_group_ad WHERE {where} AND ad_group_ad.status != 'REMOVED'""")]
    currency = next(iter(query(client, "SELECT customer.currency_code FROM customer"))).customer.currency_code
    return camps, ads, installs, currency


def _date(s):
    return s[:10] if s and s[:4].isdigit() else None


def build_entry(camps, ads, installs, currency, now=None):
    """Pure function: raw rows in, feed entry out (unknown fields omitted)."""
    now = now or datetime.now(timezone.utc)
    e = {"as_of": now.isoformat(timespec="seconds"), "source": "GAO"}
    if not camps:
        e.update(status="blocked", note="No matching App campaign found in the account")
        return e
    starts = [d for d in (_date(c["start"]) for c in camps) if d]
    if starts:
        e["start"] = min(starts)
    e["impressions"] = sum(c["impressions"] for c in camps)
    e["clicks"] = sum(c["clicks"] for c in camps)
    if installs is not None:
        e["installs"] = installs
    notes = []
    if currency == "CAD":
        e["spend"] = round(sum(c["cost"] for c in camps), 2)
    else:
        notes.append(f"spend omitted: account currency is {currency}, not CAD")

    live_ads = [a for a in ads if a["status"] != "REMOVED"]
    rank = [a["strength"] for a in live_ads if a["strength"] in STRENGTH_ORDER]
    if rank:
        e["ad_strength"] = min(rank, key=STRENGTH_ORDER.index).title()
    elif live_ads:
        e["ad_strength"] = live_ads[0]["strength"].replace("_", " ").title()

    disapproved = [a for a in live_ads if a["approval"] == "DISAPPROVED"]
    in_review = [a for a in live_ads if a["review"] in ("REVIEW_IN_PROGRESS", "UNDER_APPEAL")]
    if live_ads:
        e["review_status"] = ("Disapproved" if disapproved and len(disapproved) == len(live_ads)
                              else "In review" if in_review
                              else "Partly disapproved" if disapproved else "Approved")

    ended = [c for c in camps if _date(c["end"]) and _date(c["end"]) < now.date().isoformat()]
    if len(ended) == len(camps):
        e["status"] = "done"
    elif live_ads and len(disapproved) == len(live_ads):
        e["status"] = "blocked"
    elif all(c["status"] == "PAUSED" for c in camps):
        e["status"] = "paused"
    elif in_review and e["impressions"] == 0:
        e["status"] = "submitted"
    else:
        e["status"] = "live"
    if e["status"] == "blocked" and disapproved:
        notes.append("all ads disapproved, needs a policy fix")
    if notes:
        e["note"] = "; ".join(notes)
    return e


def write_feed(entry, path, key):
    p = Path(path)
    try:
        current = json.loads(p.read_text()) if p.exists() else {}
    except ValueError:
        current = {}
    current.setdefault("campaigns", {})[key] = entry
    p.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=p.parent, prefix=".feed-", suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(current, f, indent=2)
    os.replace(tmp, p)  # atomic: the panel never reads a half-written file


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    load_env_file()
    path = os.environ.get("JARVIS_FEED_PATH", DEFAULT_PATH)
    key = os.environ.get("JARVIS_FEED_KEY", "google-app")
    entry = build_entry(*fetch(get_client()))
    if a.dry_run:
        print(json.dumps({"campaigns": {key: entry}}, indent=2))
        return
    try:
        write_feed(entry, path, key)
    except OSError as e:
        sys.exit(f"Could not write {path}: {e}. Set JARVIS_FEED_PATH in .env.googleads.")
    print(f"Wrote {key} ({entry['status']}) to {path}")


if __name__ == "__main__":
    main()
