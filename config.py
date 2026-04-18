from pathlib import Path

APARTMENT = {
    "address": "ביאליק 21, טירת הכרמל",
    "city": "טירת כרמל",
    "rooms": 3,
    "sqm": 60,
    "floor": 3,
    "has_elevator": False,
    "has_columns": False,
}

SEARCH_CITY = "טירת כרמל"
SEARCH_ROOMS = 3

DATA_DIR = Path(__file__).parent / "data"
LISTINGS_DIR = DATA_DIR / "listings"
TRANSACTIONS_DIR = DATA_DIR / "transactions"
HISTORY_DIR = DATA_DIR / "history"

TRANSACTIONS_CSV = TRANSACTIONS_DIR / "transactions.csv"
PRICE_HISTORY_CSV = HISTORY_DIR / "price_history.csv"

CLAUDE_MODEL = "claude-sonnet-4-6"

# Alert thresholds
PRICE_CHANGE_ALERT_PCT = 3.0       # % change in avg price/sqm triggers alert
LISTING_DROP_ALERT_PCT = 20.0      # % drop in listing count triggers high-demand alert
