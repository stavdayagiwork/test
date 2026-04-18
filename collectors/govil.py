"""
Fetches closed real estate transactions from the Israeli government open data API
(Shaam - Israel Tax Authority - real estate transactions registry).

API docs: https://data.gov.il/dataset/shimshon
Resource ID for apartment transactions: b8b85823-f736-4b74-9f79-9962c4c4d25b
"""
from datetime import datetime, date, timedelta

import httpx

CKAN_API = "https://data.gov.il/api/3/action/datastore_search_sql"

# SQL query against the SHAAM dataset
QUERY_TEMPLATE = """
SELECT "SETTLEMENT_NAME", "STREET_NAME", "HOUSE_NUMBER", "FLOOR",
       "ROOMS", "DEAL_AMOUNT", "TOTAL_FLOOR_AREA", "DEAL_DATE"
FROM "b8b85823-f736-4b74-9f79-9962c4c4d25b"
WHERE "SETTLEMENT_NAME" ILIKE '%טירת כרמל%'
  AND "ROOMS" = '{rooms}'
  AND "DEAL_DATE" >= '{from_date}'
ORDER BY "DEAL_DATE" DESC
LIMIT 200
"""

HEADERS = {
    "User-Agent": "real-estate-agent/1.0 (price-tracker)",
}


def fetch_transactions(months_back: int = 24) -> list[dict]:
    from_date = (date.today() - timedelta(days=30 * months_back)).strftime("%Y-%m-%d")
    sql = QUERY_TEMPLATE.format(rooms=3, from_date=from_date)
    try:
        with httpx.Client(timeout=30) as client:
            resp = client.get(CKAN_API, params={"sql": sql}, headers=HEADERS)
            resp.raise_for_status()
            records = resp.json().get("result", {}).get("records", [])
    except Exception:
        return []

    transactions = []
    for r in records:
        price = r.get("DEAL_AMOUNT")
        sqm = r.get("TOTAL_FLOOR_AREA")
        rooms = r.get("ROOMS")
        floor_raw = r.get("FLOOR")
        deal_date = r.get("DEAL_DATE", "")[:10]  # keep YYYY-MM-DD
        street = r.get("STREET_NAME", "")
        house = r.get("HOUSE_NUMBER", "")
        city = r.get("SETTLEMENT_NAME", "")
        address = f"{street} {house}, {city}".strip()

        try:
            price_int = int(float(price)) if price else None
            sqm_float = float(sqm) if sqm else None
            price_per_sqm = round(price_int / sqm_float) if price_int and sqm_float else None
            floor_int = int(float(floor_raw)) if floor_raw else None
        except (ValueError, TypeError):
            continue

        if price_int:
            transactions.append({
                "date": deal_date,
                "address": address,
                "price": price_int,
                "sqm": sqm_float,
                "rooms": rooms,
                "floor": floor_int,
                "price_per_sqm": price_per_sqm,
                "source": "govil",
            })
    return transactions
