"""
Market analysis: statistics, price trends, demand signals, transaction velocity.
"""
from datetime import date, timedelta
from statistics import median, mean
from typing import Any

from config import PRICE_CHANGE_ALERT_PCT, LISTING_DROP_ALERT_PCT


def _prices(listings: list[dict]) -> list[float]:
    return [float(l["price"]) for l in listings if l.get("price")]


def _prices_per_sqm(listings: list[dict]) -> list[float]:
    return [
        float(l["price"]) / float(l["sqm"])
        for l in listings
        if l.get("price") and l.get("sqm") and float(l["sqm"]) > 0
    ]


def get_market_overview(listings: list[dict], transactions: list[dict]) -> dict[str, Any]:
    """Current market snapshot from active listings + recent closed deals."""
    prices = _prices(listings)
    ppsqm = _prices_per_sqm(listings)

    tx_prices = [float(t["price"]) for t in transactions if t.get("price")]
    tx_ppsqm = [
        float(t["price"]) / float(t["sqm"])
        for t in transactions
        if t.get("price") and t.get("sqm") and float(t["sqm"]) > 0
    ]

    recent_tx = [
        t for t in transactions
        if t.get("date") and t["date"] >= (date.today() - timedelta(days=90)).isoformat()
    ]

    return {
        "listing_count": len(listings),
        "avg_price": round(mean(prices)) if prices else None,
        "median_price": round(median(prices)) if prices else None,
        "avg_price_per_sqm": round(mean(ppsqm)) if ppsqm else None,
        "median_price_per_sqm": round(median(ppsqm)) if ppsqm else None,
        "min_price": round(min(prices)) if prices else None,
        "max_price": round(max(prices)) if prices else None,
        "transactions_last_90d": len(recent_tx),
        "avg_transaction_price": round(mean(tx_prices)) if tx_prices else None,
        "avg_transaction_price_per_sqm": round(mean(tx_ppsqm)) if tx_ppsqm else None,
        "total_transactions_loaded": len(transactions),
    }


def get_price_trend(history: list[dict]) -> dict[str, Any]:
    """% price change over various lookback periods."""
    if not history:
        return {}

    sorted_h = sorted(history, key=lambda x: x["date"])
    latest = sorted_h[-1]
    latest_ppsqm = float(latest["avg_price_per_sqm"]) if latest.get("avg_price_per_sqm") else None
    latest_price = float(latest["avg_price"]) if latest.get("avg_price") else None
    today = date.today()

    def _change(days: int) -> dict | None:
        cutoff = (today - timedelta(days=days)).isoformat()
        older = [h for h in sorted_h if h["date"] <= cutoff]
        if not older or not latest_ppsqm:
            return None
        ref = float(older[-1]["avg_price_per_sqm"])
        if not ref:
            return None
        pct = round((latest_ppsqm - ref) / ref * 100, 1)
        return {"pct_change": pct, "from_date": older[-1]["date"], "from_ppsqm": round(ref)}

    return {
        "latest_date": latest["date"],
        "latest_avg_price": round(latest_price) if latest_price else None,
        "latest_avg_price_per_sqm": round(latest_ppsqm) if latest_ppsqm else None,
        "change_1m": _change(30),
        "change_3m": _change(90),
        "change_6m": _change(180),
        "change_1y": _change(365),
    }


def get_demand_signals(snapshots: list[tuple[str, list[dict]]]) -> dict[str, Any]:
    """Demand indicators based on listing count trends across snapshots."""
    if len(snapshots) < 2:
        return {"message": "אין מספיק נתונים היסטוריים להשוואה (צריך לפחות 2 סריקות)"}

    counts = [(d, len(listings)) for d, listings in snapshots]
    counts.sort(key=lambda x: x[0])

    latest_date, latest_count = counts[-1]
    oldest_date, oldest_count = counts[0]

    # Compare latest vs 30 days ago
    cutoff = (date.today() - timedelta(days=30)).isoformat()
    older_counts = [(d, c) for d, c in counts if d <= cutoff]
    month_ago_count = older_counts[-1][1] if older_counts else oldest_count

    listing_delta_pct = (
        round((latest_count - month_ago_count) / month_ago_count * 100, 1)
        if month_ago_count else 0
    )

    # Detect URLs that disappeared between snapshots (possible sales)
    recent_snapshots = snapshots[-5:] if len(snapshots) >= 5 else snapshots
    url_sets = [set(l.get("url", "") for l in listings) for _, listings in recent_snapshots]
    if len(url_sets) >= 2:
        disappeared = len(url_sets[-2] - url_sets[-1])
        appeared = len(url_sets[-1] - url_sets[-2])
    else:
        disappeared = appeared = 0

    high_demand = listing_delta_pct <= -LISTING_DROP_ALERT_PCT

    return {
        "current_listing_count": latest_count,
        "listing_count_30d_ago": month_ago_count,
        "listing_delta_pct": listing_delta_pct,
        "listings_disappeared_last_scan": disappeared,
        "new_listings_last_scan": appeared,
        "high_demand_signal": high_demand,
        "snapshots_available": len(snapshots),
        "data_since": oldest_date,
    }


def get_transaction_velocity(transactions: list[dict]) -> dict[str, Any]:
    """Deals per month over the past 12 months."""
    if not transactions:
        return {}

    from collections import defaultdict
    monthly: dict[str, int] = defaultdict(int)
    for t in transactions:
        d = t.get("date", "")
        if len(d) >= 7:
            monthly[d[:7]] += 1

    sorted_months = sorted(monthly.items())
    last_12 = sorted_months[-12:]

    avg_per_month = round(sum(c for _, c in last_12) / len(last_12), 1) if last_12 else 0
    latest_month_count = last_12[-1][1] if last_12 else 0

    return {
        "avg_deals_per_month_last_12m": avg_per_month,
        "deals_latest_month": latest_month_count,
        "monthly_breakdown": dict(last_12),
    }


def detect_alerts(current_overview: dict, history: list[dict], snapshots: list[tuple]) -> list[str]:
    """Returns list of alert messages if thresholds are breached."""
    alerts = []

    trend = get_price_trend(history)
    change_1m = trend.get("change_1m")
    if change_1m and abs(change_1m["pct_change"]) >= PRICE_CHANGE_ALERT_PCT:
        direction = "עלייה" if change_1m["pct_change"] > 0 else "ירידה"
        alerts.append(
            f"⚠️ {direction} של {abs(change_1m['pct_change'])}% במחיר ממוצע למ\"ר בחודש האחרון"
        )

    demand = get_demand_signals(snapshots)
    if demand.get("high_demand_signal"):
        alerts.append(
            f"🔥 ביקוש גבוה: כמות המודעות ירדה ב-{abs(demand['listing_delta_pct'])}% בחודש האחרון"
        )

    return alerts
