"""Read-only performance report. Safe to run any time; changes nothing.

Usage:
    python -m googleads.report                # markdown report, last 30 days
    python -m googleads.report --days 7
    python -m googleads.report --json
"""
import argparse
import json

from googleads.client import get_client, money, query

def date_clause(days: int) -> str:
    from datetime import date, timedelta

    end = date.today() - timedelta(days=1)  # yesterday: today's data is partial
    start = end - timedelta(days=days - 1)
    return f"segments.date BETWEEN '{start.isoformat()}' AND '{end.isoformat()}'"


def campaigns(client, days):
    q = f"""
        SELECT campaign.id, campaign.name, campaign.status,
               campaign.advertising_channel_type, campaign.bidding_strategy_type,
               campaign_budget.resource_name, campaign_budget.amount_micros,
               metrics.cost_micros, metrics.impressions, metrics.clicks,
               metrics.conversions, metrics.conversions_value,
               metrics.search_budget_lost_impression_share,
               metrics.search_rank_lost_impression_share
        FROM campaign
        WHERE {date_clause(days)} AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC"""
    out = []
    for r in query(client, q):
        cost = money(r.metrics.cost_micros)
        conv = round(r.metrics.conversions, 2)
        out.append({
            "id": r.campaign.id,
            "name": r.campaign.name,
            "status": r.campaign.status.name,
            "type": r.campaign.advertising_channel_type.name,
            "bidding": r.campaign.bidding_strategy_type.name,
            "budget_resource": r.campaign_budget.resource_name,
            "daily_budget": money(r.campaign_budget.amount_micros),
            "cost": cost,
            "impressions": r.metrics.impressions,
            "clicks": r.metrics.clicks,
            "ctr": round(r.metrics.clicks / r.metrics.impressions * 100, 2) if r.metrics.impressions else 0,
            "conversions": conv,
            "cpa": round(cost / conv, 2) if conv else None,
            "roas": round(r.metrics.conversions_value / cost, 2) if cost else None,
            "lost_is_budget": round(r.metrics.search_budget_lost_impression_share * 100, 1),
            "lost_is_rank": round(r.metrics.search_rank_lost_impression_share * 100, 1),
        })
    return out


def wasted_search_terms(client, days, limit=25):
    q = f"""
        SELECT search_term_view.search_term, campaign.id, campaign.name,
               ad_group.name, metrics.cost_micros, metrics.clicks, metrics.conversions
        FROM search_term_view
        WHERE {date_clause(days)} AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC LIMIT 500"""
    rows = [{
        "term": r.search_term_view.search_term,
        "campaign_id": r.campaign.id,
        "campaign": r.campaign.name,
        "ad_group": r.ad_group.name,
        "cost": money(r.metrics.cost_micros),
        "clicks": r.metrics.clicks,
        "conversions": round(r.metrics.conversions, 2),
    } for r in query(client, q)]
    return [x for x in rows if x["conversions"] == 0][:limit]


def weak_keywords(client, days, limit=25):
    q = f"""
        SELECT ad_group_criterion.resource_name, ad_group_criterion.keyword.text,
               ad_group_criterion.keyword.match_type,
               ad_group_criterion.quality_info.quality_score,
               campaign.name, ad_group.name,
               metrics.cost_micros, metrics.clicks, metrics.conversions
        FROM keyword_view
        WHERE {date_clause(days)} AND ad_group_criterion.status = 'ENABLED'
              AND metrics.cost_micros > 0
        ORDER BY metrics.cost_micros DESC LIMIT 500"""
    rows = [{
        "resource": r.ad_group_criterion.resource_name,
        "keyword": r.ad_group_criterion.keyword.text,
        "match": r.ad_group_criterion.keyword.match_type.name,
        "quality_score": r.ad_group_criterion.quality_info.quality_score or None,
        "campaign": r.campaign.name,
        "ad_group": r.ad_group.name,
        "cost": money(r.metrics.cost_micros),
        "clicks": r.metrics.clicks,
        "conversions": round(r.metrics.conversions, 2),
    } for r in query(client, q)]
    return [x for x in rows if x["conversions"] == 0][:limit]


def disapproved_ads(client):
    q = """
        SELECT ad_group_ad.resource_name, ad_group_ad.policy_summary.approval_status,
               ad_group_ad.policy_summary.review_status, campaign.name, ad_group.name
        FROM ad_group_ad
        WHERE ad_group_ad.status != 'REMOVED'
          AND ad_group_ad.policy_summary.approval_status IN ('DISAPPROVED', 'AREA_OF_INTEREST_ONLY')"""
    return [{
        "resource": r.ad_group_ad.resource_name,
        "approval": r.ad_group_ad.policy_summary.approval_status.name,
        "campaign": r.campaign.name,
        "ad_group": r.ad_group.name,
    } for r in query(client, q)]


def recommendations(client):
    q = """
        SELECT recommendation.resource_name, recommendation.type, recommendation.campaign
        FROM recommendation
        WHERE recommendation.dismissed = FALSE"""
    return [{
        "resource": r.recommendation.resource_name,
        "type": r.recommendation.type_.name,
        "campaign": r.recommendation.campaign,
    } for r in query(client, q)]


def build(days):
    client = get_client()
    return {
        "days": days,
        "campaigns": campaigns(client, days),
        "wasted_search_terms": wasted_search_terms(client, days),
        "zero_conversion_keywords": weak_keywords(client, days),
        "disapproved_ads": disapproved_ads(client),
        "recommendations": recommendations(client),
    }


def table(title, rows, cols):
    lines = [f"\n## {title}"]
    if not rows:
        return "\n".join(lines + ["_none_"])
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * len(cols))
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "")) for c in cols) + " |")
    return "\n".join(lines)


def render(data):
    parts = [f"# Google Ads report (last {data['days']} days)"]
    parts.append(table("Campaigns", data["campaigns"], [
        "id", "name", "status", "daily_budget", "cost", "clicks", "ctr",
        "conversions", "cpa", "roas", "lost_is_budget", "lost_is_rank"]))
    parts.append(table("Search terms spending with no conversions", data["wasted_search_terms"],
                       ["term", "campaign", "ad_group", "cost", "clicks"]))
    parts.append(table("Keywords spending with no conversions", data["zero_conversion_keywords"],
                       ["keyword", "match", "quality_score", "campaign", "cost", "clicks"]))
    parts.append(table("Disapproved ads", data["disapproved_ads"], ["campaign", "ad_group", "approval", "resource"]))
    parts.append(table("Open recommendations", data["recommendations"], ["type", "campaign", "resource"]))
    return "\n".join(parts)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    data = build(args.days)
    print(json.dumps(data, indent=2, default=str) if args.json else render(data))


if __name__ == "__main__":
    main()
