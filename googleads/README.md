# Google Ads API setup

The API is free. You pay only for ad spend.

## One-time setup (about 20 minutes, on your own computer)

1. **Manager account.** Sign in at ads.google.com and create a free manager (MCC) account
   (ads.google.com/home/tools/manager-accounts), then link your ad account to it.
2. **Developer token.** In the manager account: Admin > API Center. Fill in the short form.
   You get a token immediately with *Test* access (test accounts only). Apply for
   *Basic* access (or *Explorer*, if offered) so it works on your real account. Approval can take a few days.
3. **OAuth client.** In console.cloud.google.com: create a project, enable **Google Ads API**,
   configure the OAuth consent screen (External, add yourself as a test user), then
   Credentials > Create credentials > **OAuth client ID** > *Desktop app*. Copy the client ID and secret.
4. **Fill in settings.** `cp .env.googleads.example .env.googleads` and enter the developer token,
   client ID, client secret, your ad account ID (`GOOGLE_ADS_CUSTOMER_ID`) and the manager account ID
   (`GOOGLE_ADS_LOGIN_CUSTOMER_ID`).
5. **Refresh token.**
   ```bash
   pip install -r googleads/requirements.txt
   python -m googleads.oauth_setup
   ```
   Approve access in the browser, then paste the printed `GOOGLE_ADS_REFRESH_TOKEN=...` line into `.env.googleads`.
6. **Test it.**
   ```bash
   python -m googleads.report --days 30
   ```

`.env.googleads` is git-ignored. Never commit it or paste it into chat.

## Commands

| Command | What it does | Who runs it |
|---|---|---|
| `python -m googleads.report [--days N] [--json]` | Read-only report: campaigns, wasted search terms, zero-conversion keywords, disapproved ads, recommendations | agent |
| `python -m googleads.actions negative-keyword --campaign-id ID --text "free" --match PHRASE` | Add a negative keyword | agent |
| `python -m googleads.actions pause --kind keyword\|ad\|ad-group --resource-name RN --reason "..."` | Pause waste | agent |
| `python -m googleads.actions apply-recommendation --resource-name RN` | Apply a recommendation. Only no-spend types run without approval | agent / you |
| `python -m googleads.actions set-budget --budget-id ID --amount 25` | Change a daily budget | **you only** |

| `python -m googleads.summary [--dry-run]` | Build the weekly summary and POST it to the Jarvis webhook (chattervane > app data panel). `--dry-run` prints the payload only | agent |

Every command accepts `--dry-run`. Changes are logged to `.claude/google-ads/changes.jsonl`.

## Budget approval

`set-budget` (and any recommendation that could change spend, bids or targeting) stops and asks you to type
`APPROVE` in a real terminal. It reads from `/dev/tty`, so the agent cannot answer for you. The agent will
tell you the exact command to run. There is no command for bids or bid strategies, so the agent cannot change them.

## Jarvis webhook

Set `JARVIS_WEBHOOK_URL` in `.env.googleads` (and `JARVIS_WEBHOOK_SECRET` if Jarvis verifies signatures).
`python -m googleads.summary` sends JSON with `app: "chattervane"`, `panel: "app-data"`, totals, top campaigns,
wasted search terms, changes made this week, items needing your approval and alerts. If Jarvis expects different
field names or a different auth header, edit `build_summary` / `post` in `googleads/summary.py`.

## Weekly review on your machine

`googleads/run_weekly.sh` runs the review with the Claude Code CLI (`claude -p`), writes the report to
`.claude/google-ads/reports/<date>.md` and sends the summary to Jarvis. It runs on your computer, so it can read
`.env.googleads`. Schedule it with cron:

```bash
crontab -e
```

then add (use your real path):

```
15 9 * * 1  /full/path/to/Youtube-SaaS/googleads/run_weekly.sh
```

The computer must be on at that time. The script allows only the report, summary and the three safe action commands,
so it cannot change budgets. Budget proposals appear in the report; you run `set-budget` yourself.

## Jarvis campaign feed (panel data file)

`python -m googleads.feed` writes `/home/sam/Projects/Jarvis/chattervane-ads-feed.json` (change with `JARVIS_FEED_PATH`):
status, spend (CA$), impressions, clicks, installs, ad strength and review status for the `google-app` entry.
Unknown fields are left out, other entries in the file are kept, and the file is replaced atomically.
Figures are lifetime totals since the campaign started. Installs come from conversions in the Download category.
Set `JARVIS_FEED_CAMPAIGN_IDS` to limit it to specific campaigns (default: all App campaigns).

The panel warns when `as_of` is over 36 hours old, so a weekly run is not enough. Refresh it daily on your machine (no AI needed):

```
5 8 * * *  cd /full/path/to/Youtube-SaaS && python -m googleads.feed
```
