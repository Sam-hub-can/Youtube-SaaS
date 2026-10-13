from datetime import timedelta
import announcer as an

PLAN = an.load_plan("announcer.example.json")


def test_stage_progression():
    s = PLAN["_start"]
    assert an.due_stage(PLAN, s - timedelta(days=4)) is None
    assert an.due_stage(PLAN, s - timedelta(days=2)) == "initial"
    assert an.due_stage(PLAN, s - timedelta(hours=2)) == "reminder_24h"
    assert an.due_stage(PLAN, s - timedelta(minutes=30)) == "reminder_1h"
    assert an.due_stage(PLAN, s + timedelta(minutes=1)) == "started"
    assert an.due_stage(PLAN, PLAN["_end"]) == "completed"


def test_message_contents():
    m = an.build_message(PLAN, "initial")
    assert "Database upgrade" in m and "120 min" in m and "reply worker" in m
    assert "back" in an.build_message(PLAN, "completed")


def test_dry_run_sends_nothing(capsys):
    assert an.announce(PLAN, "initial", send=False) == 0
    assert "[dry-run:slack]" in capsys.readouterr().out


def test_missing_env_reports_failure(monkeypatch):
    monkeypatch.delenv("ANNOUNCER_SLACK_WEBHOOK", raising=False)
    monkeypatch.delenv("ANNOUNCER_DISCORD_WEBHOOK", raising=False)
    assert an.announce(PLAN, "initial", send=True) == 2
