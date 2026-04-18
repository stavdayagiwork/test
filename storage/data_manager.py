import json
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any

from config import LISTINGS_DIR, TRANSACTIONS_CSV, PRICE_HISTORY_CSV


def _ensure_dirs():
    for d in [LISTINGS_DIR, TRANSACTIONS_CSV.parent, PRICE_HISTORY_CSV.parent]:
        d.mkdir(parents=True, exist_ok=True)


def save_listings_snapshot(listings: list[dict]) -> Path:
    _ensure_dirs()
    today = date.today().isoformat()
    path = LISTINGS_DIR / f"{today}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(listings, f, ensure_ascii=False, indent=2)
    return path


def load_latest_listings() -> list[dict]:
    _ensure_dirs()
    files = sorted(LISTINGS_DIR.glob("*.json"), reverse=True)
    if not files:
        return []
    with open(files[0], encoding="utf-8") as f:
        return json.load(f)


def load_all_snapshots() -> list[tuple[str, list[dict]]]:
    """Returns list of (date_str, listings) sorted oldest-first."""
    _ensure_dirs()
    result = []
    for path in sorted(LISTINGS_DIR.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            result.append((path.stem, json.load(f)))
    return result


def append_transactions(transactions: list[dict]):
    _ensure_dirs()
    fieldnames = ["date", "address", "price", "sqm", "rooms", "floor", "price_per_sqm", "source"]
    write_header = not TRANSACTIONS_CSV.exists() or TRANSACTIONS_CSV.stat().st_size == 0
    with open(TRANSACTIONS_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerows(transactions)


def load_transactions() -> list[dict]:
    _ensure_dirs()
    if not TRANSACTIONS_CSV.exists():
        return []
    with open(TRANSACTIONS_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def update_price_history(avg_price: float, avg_price_per_sqm: float, listing_count: int, median_price: float):
    _ensure_dirs()
    today = date.today().isoformat()
    write_header = not PRICE_HISTORY_CSV.exists() or PRICE_HISTORY_CSV.stat().st_size == 0
    with open(PRICE_HISTORY_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "avg_price", "avg_price_per_sqm", "listing_count", "median_price"])
        if write_header:
            writer.writeheader()
        writer.writerow({
            "date": today,
            "avg_price": round(avg_price),
            "avg_price_per_sqm": round(avg_price_per_sqm),
            "listing_count": listing_count,
            "median_price": round(median_price),
        })


def load_price_history() -> list[dict]:
    _ensure_dirs()
    if not PRICE_HISTORY_CSV.exists():
        return []
    with open(PRICE_HISTORY_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))
