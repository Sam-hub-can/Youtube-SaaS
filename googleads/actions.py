"""Change the account. Every command supports --dry-run (validate only).

Safe commands the agent may run on its own:
    negative-keyword, pause, apply-recommendation (allow-listed types only)

Gated commands (need YOU, typing APPROVE in a real terminal):
    set-budget, apply-recommendation for any non-allow-listed type
The gate reads from /dev/tty, so a script or agent without a terminal cannot
pass it. There is intentionally no command that changes bids or bid strategy.

Every executed change is appended to .claude/google-ads/changes.jsonl.
"""
import argparse
import json
import sys
from datetime import datetime, timezone

from googleads.client import LOG_FILE, customer_id, get_client, money, query

# Recommendation types that improve ads without changing spend or targeting.
SAFE_RECOMMENDATIONS = {
    "SITELINK_ASSET", "CALLOUT_ASSET", "CALL_ASSET",
    "RESPONSIVE_SEARCH_AD_ASSET", "RESPONSIVE_SEARCH_AD_IMPROVE_AD_STRENGTH",
    "IMPROVE_PERFORMANCE_MAX_AD_STRENGTH", "IMPROVE_DEMAND_GEN_AD_STRENGTH",
    "OPTIMIZE_AD_ROTATION",
}


def log(action: str, detail: dict, dry_run: bool) -> None:
    if dry_run:
        return
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": datetime.now(timezone.utc).isoformat(), "action": action, **detail}
    with LOG_FILE.open("a") as f:
        f.write(json.dumps(entry) + "\n")


def require_human(summary: str) -> None:
    """Hard gate: a human must type APPROVE on the terminal."""
    print("\nAPPROVAL REQUIRED\n" + summary)
    try:
        with open("/dev/tty") as tty:
            print("Type APPROVE to continue: ", end="", flush=True)
            answer = tty.readline().strip()
    except OSError:
        sys.exit("Refused: no interactive terminal. Run this command yourself in a terminal.")
    if answer != "APPROVE":
        sys.exit("Not approved. Nothing changed.")


def cmd_negative_keyword(client, a):
    op = client.get_type("CampaignCriterionOperation")
    crit = op.create
    crit.campaign = client.get_service("CampaignService").campaign_path(customer_id(), a.campaign_id)
    crit.negative = True
    crit.keyword.text = a.text
    crit.keyword.match_type = client.enums.KeywordMatchTypeEnum[a.match]
    resp = client.get_service("CampaignCriterionService").mutate_campaign_criteria(
        customer_id=customer_id(), operations=[op], validate_only=a.dry_run)
    print(("Validated" if a.dry_run else "Added") + f" negative [{a.match}] '{a.text}' on campaign {a.campaign_id}")
    log("negative-keyword", {"campaign_id": a.campaign_id, "text": a.text, "match": a.match,
                             "result": [r.resource_name for r in resp.results]}, a.dry_run)


def cmd_pause(client, a):
    cid = customer_id()
    if a.kind == "keyword":
        svc, method, op_type, field = "AdGroupCriterionService", "mutate_ad_group_criteria", "AdGroupCriterionOperation", "ad_group_criterion"
        status_enum = client.enums.AdGroupCriterionStatusEnum.PAUSED
    elif a.kind == "ad":
        svc, method, op_type, field = "AdGroupAdService", "mutate_ad_group_ads", "AdGroupAdOperation", "ad_group_ad"
        status_enum = client.enums.AdGroupAdStatusEnum.PAUSED
    else:
        svc, method, op_type, field = "AdGroupService", "mutate_ad_groups", "AdGroupOperation", "ad_group"
        status_enum = client.enums.AdGroupStatusEnum.PAUSED
    op = client.get_type(op_type)
    op.update.resource_name = a.resource_name
    op.update.status = status_enum
    op.update_mask.paths.append("status")
    getattr(client.get_service(svc), method)(customer_id=cid, operations=[op], validate_only=a.dry_run)
    print(("Validated pause of " if a.dry_run else "Paused ") + a.resource_name)
    log("pause", {"kind": a.kind, "resource": a.resource_name, "reason": a.reason}, a.dry_run)


def recommendation_type(client, resource_name):
    q = f"SELECT recommendation.type FROM recommendation WHERE recommendation.resource_name = '{resource_name}'"
    for r in query(client, q):
        return r.recommendation.type_.name
    sys.exit("Recommendation not found (it may already be applied or expired).")


def cmd_apply_recommendation(client, a):
    rtype = recommendation_type(client, a.resource_name)
    if rtype not in SAFE_RECOMMENDATIONS:
        require_human(f"Recommendation type {rtype} can change spend, bids or targeting.\n"
                      f"Resource: {a.resource_name}")
    op = client.get_type("ApplyRecommendationOperation")
    op.resource_name = a.resource_name
    if a.dry_run:
        print(f"Would apply {rtype}: {a.resource_name}")
        return
    client.get_service("RecommendationService").apply_recommendation(
        customer_id=customer_id(), operations=[op])
    print(f"Applied {rtype}: {a.resource_name}")
    log("apply-recommendation", {"type": rtype, "resource": a.resource_name}, False)


def cmd_set_budget(client, a):
    q = ("SELECT campaign_budget.resource_name, campaign_budget.name, campaign_budget.amount_micros "
         f"FROM campaign_budget WHERE campaign_budget.id = {a.budget_id}")
    row = next(iter(query(client, q)), None)
    if row is None:
        sys.exit(f"Budget {a.budget_id} not found.")
    current = money(row.campaign_budget.amount_micros)
    summary = (f"Budget '{row.campaign_budget.name}' (id {a.budget_id}): "
               f"daily {current} -> {a.amount} ({(a.amount - current) / current * 100:+.0f}%)"
               if current else f"Budget {a.budget_id}: set daily to {a.amount}")
    if not a.dry_run:
        require_human(summary)
    op = client.get_type("CampaignBudgetOperation")
    op.update.resource_name = row.campaign_budget.resource_name
    op.update.amount_micros = int(round(a.amount * 1_000_000))
    op.update_mask.paths.append("amount_micros")
    client.get_service("CampaignBudgetService").mutate_campaign_budgets(
        customer_id=customer_id(), operations=[op], validate_only=a.dry_run)
    print(("Validated: " if a.dry_run else "Done: ") + summary)
    log("set-budget", {"budget_id": a.budget_id, "from": current, "to": a.amount}, a.dry_run)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, **kw):
        sp = sub.add_parser(name, **kw)
        sp.add_argument("--dry-run", action="store_true", help="validate only, change nothing")
        sp.set_defaults(fn=fn)
        return sp

    s = add("negative-keyword", cmd_negative_keyword, help="add a campaign-level negative keyword")
    s.add_argument("--campaign-id", required=True)
    s.add_argument("--text", required=True)
    s.add_argument("--match", choices=["EXACT", "PHRASE", "BROAD"], default="PHRASE")

    s = add("pause", cmd_pause, help="pause a keyword, ad or ad group")
    s.add_argument("--kind", choices=["keyword", "ad", "ad-group"], required=True)
    s.add_argument("--resource-name", required=True)
    s.add_argument("--reason", required=True, help="why (goes in the change log)")

    s = add("apply-recommendation", cmd_apply_recommendation, help="apply a Google recommendation")
    s.add_argument("--resource-name", required=True)

    s = add("set-budget", cmd_set_budget, help="change a daily budget (needs your terminal approval)")
    s.add_argument("--budget-id", required=True)
    s.add_argument("--amount", type=float, required=True, help="new daily budget in account currency")

    a = p.parse_args()
    a.fn(get_client(), a)


if __name__ == "__main__":
    main()
