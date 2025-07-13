import requests
import re
import time
import sqlite3
from datetime import datetime
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

DB_FILE = "seen_ids.db"
BERLIN_TZ = ZoneInfo("Europe/Berlin")
BASE_URL = "https://inberlinwohnen.de/"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            url TEXT,
            price REAL,
            price_warm REAL,
            size REAL,
            address TEXT,
            lat REAL,
            lon REAL,
            swapflat INTEGER,
            wbs_required INTEGER,
            created_at TEXT,
            source_immoscout INTEGER,
            source_kleinanzeigen INTEGER,
            source_immowelt INTEGER,
            photo_url TEXT,
            is_active TEXT,
            last_checked TEXT,
            source_wggesucht INTEGER,
            source_inberlinwohnen INTEGER
        )
    """)
    conn.commit()
    return conn, cursor


def mark_as_seen(conn, cursor, obj_id, listing):
    cursor.execute("""
        INSERT OR IGNORE INTO listings (
            id, url, price, price_warm, size, address, lat, lon, swapflat,
            wbs_required, created_at, source_immoscout, source_kleinanzeigen,
            source_immowelt, photo_url, is_active, last_checked,
            source_wggesucht, source_inberlinwohnen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        obj_id,
        listing["url"],
        listing["price"],
        None,
        listing["size"],
        listing["address"],
        listing["lat"],
        listing["lon"],
        0,
        int(listing["wbs_required"]),
        datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0, 0, 0,
        listing["photo_url"],
        "1",
        datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0,
        1
    ))
    conn.commit()


def geocode_address(address):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "limit": 1}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; InBerlinBot/1.0)"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            lat = float(data[0]["lat"])
            lon = float(data[0]["lon"])
            print(f"{lat}, {lon} ← {address}")
            return lat, lon
    except Exception:
        pass
    return None, None


def clean_price_size(value):
    if not value:
        return None
    val = value.replace("\xa0", "").replace("€", "").replace("m²", "").strip()
    val = val.replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


def is_wbs_required(text):
    text = text.lower()
    return "wbs" in text and "ohne" not in text or "wohnberechtigungsschein" in text


def fetch_inberlin_listings(seen_ids):
    url = "https://inberlinwohnen.de/wp-content/themes/ibw/skript/wohnungsfinder.php"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "X-Requested-With": "XMLHttpRequest",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://inberlinwohnen.de",
        "Referer": "https://inberlinwohnen.de/wohnungsfinder/"
    }
    data = {
        "q": "wf-save-srch",
        "save": "false",
        "wbs": "all"
    }

    response = requests.post(url, headers=headers, data=data)
    response.raise_for_status()
    json_data = response.json()

    html = json_data.get("searchresults", "")
    soup = BeautifulSoup(html, "html.parser")
    flats = soup.select("li.tb-merkflat")

    listings = []

    for flat in flats:
        raw_id = flat.get("id", "")
        if not raw_id:
            continue

        flat_id = raw_id.replace("flat_", "").strip()
        if flat_id in seen_ids:
            continue  # skip

        title_tag = flat.select_one("h3 span._tb_left")
        address_tag = flat.select_one("table.tb-small-data a.map-but")
        img_tag = flat.select_one("figure.flat-image")
        url_tag = flat.select_one("a.org-but")

        if not all([title_tag, address_tag, url_tag]):
            continue

        text = flat.get_text(" ")
        size_match = re.search(r"([\d.,]+)\s*m²", text)
        price_match = re.search(r"([\d.,]+)\s*€", text)

        size = clean_price_size(size_match.group(1)) if size_match else None
        price = clean_price_size(price_match.group(1)) if price_match else None
        address = address_tag.get_text(strip=True)

        img_url = ""
        if img_tag and "style" in img_tag.attrs:
            style = img_tag["style"]
            match = re.search(r"url\(['\"]?(.*?)['\"]?\)", style)
            if match:
                candidate_url = match.group(1)
                if "flat-dummy.jpg" not in candidate_url:  # 🛑 фильтрация заглушки
                    img_url = candidate_url



        listing = {
            "id": flat_id,
            "url": BASE_URL.rstrip("/") + url_tag.get("href", ""),
            "price": price,
            "size": size,
            "address": address,
            "lat": None,
            "lon": None,
            "photo_url": img_url,
            "wbs_required": is_wbs_required(text)
        }

        listings.append(listing)

    return listings


def run():
    conn, cursor = init_db()
    try:
        cursor.execute("SELECT id FROM listings")
        seen_ids = set(row[0] for row in cursor.fetchall())

        listings = fetch_inberlin_listings(seen_ids)
        added_count = 0

        for listing in listings:
            print(f"{listing['id']} →", end=" ")
            lat, lon = geocode_address(listing["address"])
            listing["lat"] = lat
            listing["lon"] = lon
            time.sleep(1)

        for listing in listings:
            mark_as_seen(conn, cursor, listing["id"], listing)
            added_count += 1

        print(f"\n✅ Добавлено: {added_count}")
    except Exception as e:
        print(f"🔥 Ошибка выполнения: {str(e)}")
    finally:
        conn.close()


if __name__ == "__main__":
    run()
