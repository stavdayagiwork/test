"""
Scrapes Yad2 for 3-room apartment listings in Tirat HaCarmel.
Uses httpx with realistic headers; falls back to Playwright if JS-rendered.
"""
import json
import re
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from config import SEARCH_CITY, SEARCH_ROOMS

YAD2_SEARCH_URL = (
    "https://www.yad2.co.il/realestate/forsale"
    "?city=7500&rooms={rooms_min}-{rooms_max}&priceOnly=1"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.yad2.co.il/",
}


def _parse_listings_from_next_data(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return []
    try:
        data = json.loads(script.string)
        feed = (
            data.get("props", {})
            .get("pageProps", {})
            .get("dehydratedState", {})
            .get("queries", [{}])[0]
            .get("state", {})
            .get("data", {})
            .get("feed_items", [])
        )
        listings = []
        for item in feed:
            if item.get("type") == "ad":
                row = item.get("row", {})
                price = row.get("price")
                sqm = row.get("square_meters") or row.get("SquareMeter")
                rooms = row.get("rooms")
                floor = row.get("floor")
                address = row.get("address_str") or row.get("street")
                neighborhood = row.get("neighborhood")
                city = row.get("city_text", "")
                url = "https://www.yad2.co.il/item/" + str(row.get("id", ""))
                if price and rooms:
                    listings.append({
                        "source": "yad2",
                        "price": int(price) if price else None,
                        "sqm": int(sqm) if sqm else None,
                        "rooms": float(rooms) if rooms else None,
                        "floor": int(floor) if floor else None,
                        "address": f"{address}, {neighborhood}, {city}".strip(", "),
                        "elevator": row.get("elevator"),
                        "url": url,
                        "scraped_at": datetime.now().isoformat(),
                    })
        return listings
    except (KeyError, IndexError, json.JSONDecodeError):
        return []


def _fetch_with_playwright(url: str) -> str:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({"Accept-Language": "he-IL,he;q=0.9"})
        page.goto(url, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()
    return html


def fetch_listings() -> list[dict]:
    url = YAD2_SEARCH_URL.format(rooms_min=SEARCH_ROOMS, rooms_max=SEARCH_ROOMS)
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as client:
            resp = client.get(url)
            resp.raise_for_status()
            listings = _parse_listings_from_next_data(resp.text)
            if listings:
                return listings
    except Exception:
        pass

    # Fallback: Playwright
    try:
        html = _fetch_with_playwright(url)
        return _parse_listings_from_next_data(html)
    except Exception:
        return []
