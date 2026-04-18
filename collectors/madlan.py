"""
Scrapes Madlan for 3-room apartment listings in Tirat HaCarmel.
Madlan embeds listing data in __NEXT_DATA__ JSON on their search page.
"""
import json
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from config import SEARCH_CITY, SEARCH_ROOMS

MADLAN_SEARCH_URL = (
    "https://www.madlan.co.il/for-sale/apartments/%D7%98%D7%99%D7%A8%D7%AA-%D7%9B%D7%A8%D7%9E%D7%9C"
    "?roomsRange={rooms}-{rooms}&condoType=apartment"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "he-IL,he;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.madlan.co.il/",
}


def _parse_next_data(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return []
    try:
        data = json.loads(script.string)
        # Navigate to listings - Madlan's structure varies; try multiple paths
        props = data.get("props", {}).get("pageProps", {})
        listings_raw = (
            props.get("initialData", {}).get("listings", [])
            or props.get("dehydratedState", {}).get("queries", [{}])[0]
            .get("state", {}).get("data", {}).get("listings", [])
        )
        listings = []
        for item in listings_raw:
            price = item.get("price") or item.get("dealInfo", {}).get("price")
            sqm = item.get("size") or item.get("property", {}).get("size")
            rooms = item.get("rooms") or item.get("property", {}).get("rooms")
            floor = item.get("floor") or item.get("property", {}).get("floor")
            address = (
                item.get("address", {}).get("street", "")
                + " "
                + str(item.get("address", {}).get("houseNum", ""))
            ).strip()
            listing_id = item.get("id") or item.get("listingId")
            url = f"https://www.madlan.co.il/listing/{listing_id}" if listing_id else ""
            elevator = item.get("elevator") or item.get("property", {}).get("elevator")
            if price and rooms:
                listings.append({
                    "source": "madlan",
                    "price": int(price),
                    "sqm": int(sqm) if sqm else None,
                    "rooms": float(rooms),
                    "floor": int(floor) if floor else None,
                    "address": address,
                    "elevator": elevator,
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
    url = MADLAN_SEARCH_URL.format(rooms=SEARCH_ROOMS)
    try:
        with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=20) as client:
            resp = client.get(url)
            resp.raise_for_status()
            listings = _parse_next_data(resp.text)
            if listings:
                return listings
    except Exception:
        pass

    try:
        html = _fetch_with_playwright(url)
        return _parse_next_data(html)
    except Exception:
        return []
