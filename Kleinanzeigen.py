# -*- coding: utf-8 -*-
import requests
import sqlite3
import re
import datetime
import time
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo

DB_FILE = "seen_ids.db"
BERLIN_TZ = ZoneInfo("Europe/Berlin")


def safe_execute(cursor, query, params=(), retries=3, delay=2):
    for attempt in range(retries):
        try:
            cursor.execute(query, params)
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e).lower():
                print(f"🔒 database is locked, retrying {attempt + 1}/{retries}...")
                time.sleep(delay)
            else:
                raise
    raise sqlite3.OperationalError("database is locked (max retries exceeded)")


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



def was_seen(cursor, obj_id):
    cursor.execute("SELECT 1 FROM listings WHERE id = ?", (obj_id,))
    return cursor.fetchone() is not None


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
        listing["price_warm"],
        listing["size"],
        listing["address"],
        listing["lat"],
        listing["lon"],
        int(listing["swapflat"]),
        int(listing["wbs_required"]),
        datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0,  # source_immoscout
        1,  # source_kleinanzeigen
        0,  # source_immowelt
        listing["photo_url"],
        "1",
        datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0,  # source_wggesucht
        0   # source_inberlinwohnen
    ))
    conn.commit()



def geocode_address(address):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "addressdetails": 1, "limit": 1}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; KleinanzeigenBot/1.0)"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except:
        pass
    return None, None


def fetch_html(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; KleinanzeigenBot/1.0)",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except Exception as e:
        print(f"❌ Ошибка при запросе {url}: {e}")
        return None


def extract_warmmiete_from_soup(soup):
    kalt = neben = warm = None
    details = soup.select("li.addetailslist--detail")
    for item in details:
        label = item.get_text(strip=True).lower()
        value_el = item.select_one(".addetailslist--detail--value")
        if not value_el:
            continue
        value_text = value_el.get_text(strip=True)
        value_text_clean = value_text.replace(".", "").replace(",", ".").replace("€", "").strip()
        try:
            number = float(re.search(r"[\d.]+", value_text_clean).group())
        except:
            continue

        if "warmmiete" in label:
            warm = number
        elif "nebenkosten" in label:
            neben = number
        elif "kaltmiete" in label:
            kalt = number

    if warm is not None:
        return warm
    if kalt is not None and neben is not None:
        return kalt + neben
    if kalt is not None:
        return kalt
    return None



def extract_data(soup):
    entries = []
    container = soup.find(id="srchrslt-adtable")
    if container is None:
        print("⚠️ Страница не загружена или структура изменилась (srchrslt-adtable не найден)")
        return entries

    exposes = container.find_all("article", class_="aditem")
    for expose in exposes:
        title_elem = expose.find(class_="ellipsis")
        if not title_elem or not title_elem.get("href"):
            continue
        url = "https://www.kleinanzeigen.de" + title_elem.get("href")

        try:
            price_text = expose.find(class_="aditem-main--middle--price-shipping--price").text.strip()
            price_match = re.search(r"[\d,.]+", price_text)
            price = float(price_match.group().replace(".", "").replace(",", ".")) if price_match else None

            tags = expose.find_all(class_="simpletag")
            size_text = tags[0].text.strip() if tags else ""
            size_match = re.search(r"[\d,.]+", size_text)
            size = float(size_match.group().replace(".", "").replace(",", ".")) if size_match else None

            address_el = expose.find("div", {"class": "aditem-main--top--left"})
        except AttributeError:
            continue

        address = address_el.text.strip().replace('\n', ' ').replace('\r', '')
        address = " ".join(address.split())
        obj_id = expose.get("data-adid")
        if not obj_id:
            continue

        lat, lon = geocode_address(address)

        images = []
        soup_detail = fetch_html(url)
        if soup_detail:
            all_imgs = soup_detail.find_all("img")
            for img in all_imgs:
                src = img.get("src") or ""
                if src.startswith("https://img.kleinanzeigen.de/api/v1/prod-ads/images/"):
                    images.append(src)
                if len(images) >= 5:
                    break

            price_warm = extract_warmmiete_from_soup(soup_detail)
        else:
            price_warm = None

        photo_url = ",".join(images)

        entry = {
            'id': str(obj_id),
            'image': images[0] if images else None,
            'url': url,
            'title': title_elem.text.strip(),
            'price': price,
            'price_warm': price_warm,
            'size': size,
            'address': address,
            'lat': lat,
            'lon': lon,
            'swapflat': 'tausch' in title_elem.text.lower(),
            'wbs_required': False,
            'photo_url': photo_url
        }
        entries.append(entry)

    return entries


def run(url=None):
    conn, cursor = init_db()
    try:
        url = url or "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203+wohnung_mieten.swap_s:nein"
        soup = fetch_html(url)

        if soup is None:
            print("❌ Не удалось получить HTML — пропуск.")
            return False

        entries = extract_data(soup)

        now = datetime.datetime.now(BERLIN_TZ).isoformat(timespec='seconds')
        print(f"\n📌 Поиск новых объявлений после {now}...")

        if not entries:
            print("⚠️ Не удалось получить объявления (возможно, структура страницы изменилась).")
            return False

        new_entries = 0
        ids = [entry['id'] for entry in entries if not was_seen(cursor, entry['id'])]
        print(f"✅ Найдено {len(ids)} новых объектов: {ids}")

        for entry in entries:
            if was_seen(cursor, entry['id']):
                continue
            new_entries += 1
            print(f"{new_entries}. 🏠 {entry['address']} | {entry['price']}€ | {entry['size']} m² | Warmmiete: {entry.get('price_warm')}")
            print(f"   🔗 {entry['url']}")
            mark_as_seen(conn, cursor, entry['id'], entry)

        if new_entries == 0:
            print("📬 Новых объявлений не найдено.")

        return new_entries > 0

    except Exception as e:
        print(f"🔥 Критическая ошибка в run_kleinanzeigen(): {e}")
        return False

    finally:
        conn.close()


if __name__ == "__main__":
    run()
