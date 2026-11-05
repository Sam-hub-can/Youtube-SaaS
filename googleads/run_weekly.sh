#!/usr/bin/env bash
# Weekly Google Ads review, run from YOUR machine (where .env.googleads lives).
# Schedule with cron, e.g. every Monday at 9:15:
#   15 9 * * 1  /full/path/to/Youtube-SaaS/googleads/run_weekly.sh
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env.googleads ]; then
  echo "Missing .env.googleads. See googleads/README.md." >&2
  exit 1
fi

mkdir -p .claude/google-ads/reports
OUT=".claude/google-ads/reports/$(date +%F).md"

# Budget changes cannot be made here: set-budget needs you to type APPROVE in a terminal.
claude -p "Run the weekly Google Ads review using the google-ads-operator agent in .claude/agents/google-ads-operator.md.
1. Read .claude/google-ads/notes.md.
2. Run python -m googleads.report --days 7 and --days 30. If settings or auth are missing, stop and say exactly what is missing.
3. Apply only the low-risk changes the agent file allows (use --dry-run first). Never change budgets, bids, bid strategy or targeting; list proposals with the exact set-budget command for me to run myself.
4. Update .claude/google-ads/notes.md.
5. Run python -m googleads.summary to send the summary to Jarvis; if it fails, say so and do not retry in a loop.
6. Finish with: Snapshot, Changed, Needs your approval, Watching, and whether the Jarvis send worked." \
  --allowedTools "Read" "Edit" "Write" "Bash(python -m googleads.report:*)" "Bash(python -m googleads.summary:*)" \
    "Bash(python -m googleads.actions negative-keyword:*)" "Bash(python -m googleads.actions pause:*)" \
    "Bash(python -m googleads.actions apply-recommendation:*)" \
  | tee "$OUT"
