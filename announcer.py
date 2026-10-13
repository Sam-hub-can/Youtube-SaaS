"""Announcer: tell everyone about a maintenance window for all servers and apps.

Usage:
    python announcer.py plan.json              # dry run (default): print messages
    python announcer.py plan.json --send       # actually deliver
    python announcer.py plan.json --send --stage reminder_1h

plan.json example (see announcer.example.json):
{
  "title": "Database upgrade",
  "start": "2026-10-20T02:00:00+00:00",
  "end":   "2026-10-20T04:00:00+00:00",
  "reason": "Upgrading PostgreSQL.",
  "targets": ["web dashboard", "reply worker", "api"],
  "channels": [
    {"type": "slack",   "url_env": "ANNOUNCER_SLACK_WEBHOOK"},
    {"type": "discord", "url_env": "ANNOUNCER_DISCORD_WEBHOOK"},
    {"type": "webhook", "url_env": "ANNOUNCER_WEBHOOK"},
    {"type": "console"}
  ]
}
Webhook URLs come from environment variables, never from the plan file.
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

STAGES = {
    # name: how long before start the stage is due (None = tied to end)
    "initial": timedelta(days=3),
    "reminder_24h": timedelta(hours=24),
    "reminder_1h": timedelta(hours=1),
    "started": timedelta(0),
    "completed": None,
}


def parse_time(value):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        raise ValueError(f"timestamp needs a timezone offset: {value!r}")
    return dt.astimezone(timezone.utc)


def load_plan(path):
    with open(path) as f:
        plan = json.load(f)
    for key in ("title", "start", "end", "targets"):
        if not plan.get(key):
            raise ValueError(f"plan is missing {key!r}")
    plan["_start"], plan["_end"] = parse_time(plan["start"]), parse_time(plan["end"])
    if plan["_end"] <= plan["_start"]:
        raise ValueError("end must be after start")
    return plan


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M UTC")


def due_stage(plan, now=None):
    """Latest stage whose time has passed, or None if before the first one."""
    now = now or datetime.now(timezone.utc)
    due = None
    for name, lead in STAGES.items():
        at = plan["_end"] if lead is None else plan["_start"] - lead
        if now >= at:
            due = name
    return due


def build_message(plan, stage):
    start, end = plan["_start"], plan["_end"]
    minutes = int((end - start).total_seconds() // 60)
    targets = ", ".join(plan["targets"])
    reason = f"\nReason: {plan['reason']}" if plan.get("reason") else ""
    window = f"{fmt(start)} to {fmt(end)} (~{minutes} min)"
    heads = {
        "initial": f"Scheduled maintenance: {plan['title']}",
        "reminder_24h": f"Reminder, maintenance in 24 hours: {plan['title']}",
        "reminder_1h": f"Reminder, maintenance starts in 1 hour: {plan['title']}",
        "started": f"Maintenance has started: {plan['title']}",
        "completed": f"Maintenance complete: {plan['title']}",
    }
    if stage == "completed":
        body = f"All services are back: {targets}."
    else:
        body = f"Window: {window}\nAffected: {targets}{reason}"
    return f"{heads[stage]}\n{body}"


def post_json(url, payload):
    req = urllib.request.Request(
        url, json.dumps(payload).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def deliver(channel, text, plan, stage):
    kind = channel["type"]
    if kind == "console":
        print(text)
        return
    url = os.getenv(channel.get("url_env", ""))
    if not url:
        raise RuntimeError(f"{channel.get('url_env')} is not set")
    if kind == "slack":
        post_json(url, {"text": text})
    elif kind == "discord":
        post_json(url, {"content": text})
    elif kind == "webhook":
        post_json(url, {"stage": stage, "title": plan["title"], "start": plan["start"],
                        "end": plan["end"], "targets": plan["targets"], "text": text})
    else:
        raise ValueError(f"unknown channel type {kind!r}")


def announce(plan, stage, send=False):
    text = build_message(plan, stage)
    failures = 0
    for ch in plan.get("channels", [{"type": "console"}]):
        label = ch["type"]
        if not send and label != "console":
            print(f"[dry-run:{label}]\n{text}\n")
            continue
        try:
            deliver(ch, text, plan, stage)
            print(f"[sent:{label}] {stage}")
        except Exception as e:
            failures += 1
            print(f"[failed:{label}] {e}", file=sys.stderr)
    return failures


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("plan")
    p.add_argument("--send", action="store_true", help="deliver (default is dry run)")
    p.add_argument("--stage", choices=list(STAGES), help="force a stage instead of auto")
    a = p.parse_args(argv)
    plan = load_plan(a.plan)
    stage = a.stage or due_stage(plan)
    if stage is None:
        print("Nothing due yet.")
        return 0
    return 1 if announce(plan, stage, a.send) else 0


if __name__ == "__main__":
    sys.exit(main())
