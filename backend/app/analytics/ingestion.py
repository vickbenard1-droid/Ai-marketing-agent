"""
Ingestion translators.

One function per source, each translating that source's own real raw
response shape into a normalized dict this app's sync orchestrator can
write into MetricSnapshot rows. Every translator is a pure function
(dict/list in, list of normalized dicts out) - no DB access, no network
calls - so each can be tested in complete isolation from the actual
source client that fetches the raw data.

Key unit-conversion decisions, each handling a genuinely different raw
shape correctly rather than assuming they're the same:
- Google Ads reports cost in MICROS (millionths of the account
  currency) - dividing by 10,000 (not 100) converts micros to cents.
- GA4 reports dates as compact YYYYMMDD strings and every metric value
  as a string, regardless of type - both need explicit parsing.
- Shopify/WooCommerce orders are aggregated by day here (translators
  receive a list of individual orders, return one row per day) -
  cancelled/refunded orders are counted toward purchase COUNT (a
  legitimate business fact: an order was placed) but excluded from
  REVENUE (money that was ultimately not kept) - this specific
  accounting choice is applied identically to both platforms.
"""
from collections import defaultdict
from datetime import date as date_type
from typing import Optional


def translate_google_ads_rows(rows: list) -> list:
    """rows: Google Ads Query Language search results, each with
    campaign/segments/metrics nested objects."""
    normalized = []
    for row in rows:
        try:
            campaign = row["campaign"]
            segments = row["segments"]
            metrics = row["metrics"]
            normalized.append(
                {
                    "external_campaign_id": str(campaign["id"]),
                    "date": date_type.fromisoformat(segments["date"]),
                    "impressions": int(metrics.get("impressions", 0)),
                    "clicks": int(metrics.get("clicks", 0)),
                    "spend_cents": round(int(metrics.get("costMicros", 0)) / 10000),
                    "purchases_count": round(float(metrics.get("conversions", 0))) if metrics.get("conversions") is not None else None,
                    "revenue_cents": round(float(metrics.get("conversionsValue", 0)) * 100) if metrics.get("conversionsValue") is not None else None,
                }
            )
        except (KeyError, ValueError, TypeError):
            continue  # a malformed row is skipped, not fatal to the whole sync
    return normalized


def translate_ga4_rows(rows: list) -> list:
    """rows: GA4 Data API rows, with date as compact YYYYMMDD and every
    value as a string regardless of underlying type."""
    normalized = []
    for row in rows:
        try:
            raw_date = row["date"]
            parsed_date = date_type(int(raw_date[0:4]), int(raw_date[4:6]), int(raw_date[6:8]))
            normalized.append(
                {
                    "source_name": row.get("sessionSource", "unknown"),
                    "campaign_name": row.get("sessionCampaignName"),
                    "date": parsed_date,
                    "clicks": int(float(row.get("sessions", 0))),
                    "purchases_count": int(float(row["conversions"])) if row.get("conversions") is not None else None,
                    "revenue_cents": round(float(row["totalRevenue"]) * 100) if row.get("totalRevenue") is not None else None,
                }
            )
        except (KeyError, ValueError, TypeError):
            continue
    return normalized


def _translate_ecommerce_orders(orders: list, *, date_field: str, total_field: str, is_cancelled) -> list:
    by_day = defaultdict(lambda: {"purchases_count": 0, "revenue_cents": 0})
    for order in orders:
        try:
            raw_date = order[date_field]
            order_date = date_type.fromisoformat(raw_date[:10])
            total_cents = round(float(order[total_field]) * 100)
        except (KeyError, ValueError, TypeError):
            continue

        by_day[order_date]["purchases_count"] += 1  # every real order counts toward the count, cancelled or not
        if not is_cancelled(order):
            by_day[order_date]["revenue_cents"] += total_cents  # only non-cancelled orders count toward revenue

    return [{"date": d, "purchases_count": v["purchases_count"], "revenue_cents": v["revenue_cents"]} for d, v in sorted(by_day.items())]


def translate_shopify_orders(orders: list) -> list:
    return _translate_ecommerce_orders(
        orders, date_field="created_at", total_field="total_price", is_cancelled=lambda o: o.get("cancelled_at") is not None
    )


def translate_woocommerce_orders(orders: list) -> list:
    return _translate_ecommerce_orders(
        orders, date_field="date_created", total_field="total", is_cancelled=lambda o: o.get("status") in ("cancelled", "refunded")
    )
