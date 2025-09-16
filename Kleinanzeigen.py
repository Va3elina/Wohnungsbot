# -*- coding: utf-8 -*-
import requests
import sqlite3
import re
import datetime
import time
import logging
import os
from bs4 import BeautifulSoup
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# === Загрузка .env ===
load_dotenv()

# === Логирование ===
LOG_FILE = os.getenv("LOG_FILE", "kleinanzeigen_scraper.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# === Константы ===
DB_FILE = os.getenv("DB_FILE", "seen_ids.db")
BERLIN_TZ = ZoneInfo("Europe/Berlin")
BASE_URL = "https://www.kleinanzeigen.de/s-wohnung-mieten/berlin/c203+wohnung_mieten.swap_s:nein"

# === Работа с БД ===
def init_db():
    """Создание базы и таблицы listings при необходимости"""
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


def was_seen(cursor, obj_id: str) -> bool:
    cursor.execute("SELECT 1 FROM listings WHERE id = ?", (obj_id,))
    return cursor.fetchone() is not None


def mark_as_seen(conn, cursor, obj_id: str, listing: dict):
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
        datetime.datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0,  # source_immoscout
        1,  # source_kleinanzeigen
        0,  # source_immowelt
        listing["photo_url"],
        "1",
        datetime.datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0,  # source_wggesucht
        0   # source_inberlinwohnen
    ))
    conn.commit()

# === Вспомогательные функции ===
def geocode_address(address):
    """Получает координаты по адресу через OpenStreetMap"""
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": address, "format": "json", "addressdetails": 1, "limit": 1}
        headers = {"User-Agent": "Mozilla/5.0 (compatible; KleinanzeigenBot/1.0)"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        if data:
            return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception:
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
        logging.error(f"❌ Ошибка при запросе {url}: {e}")
        return None


def extract_warmmiete_from_soup(soup):
    """Извлекает warmmiete из деталей объявления"""
    kalt = neben = warm = None
    details = soup.select("li.addetailslist--detail")
    for item in details:
        label = item.get_text(strip=True).lower()
        value_el = item.select_one(".addetailslist--detail--value")
        if not value_el:
            continue
        value_text = value_el.get_text(strip=True)
        try:
            number = float(re.search(r"[\d,.]+", value_text.replace(".", "").replace(",", ".")))
        except Exception:
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
    return kalt


def extract_data(soup):
    """Парсит список объявлений со страницы"""
    entries = []
    container = soup.find(id="srchrslt-adtable")
    if not container:
        logging.warning("⚠️ srchrslt-adtable не найден — структура сайта изменилась?")
        return entries

    exposes = container.find_all("article", class_="aditem")
    for expose in exposes:
        title_elem = expose.find(class_="ellipsis")
        if not title_elem or not title_elem.get("href"):
            continue
        url = "https://www.kleinanzeigen.de" + title_elem.get("href")

        obj_id = expose.get("data-adid")
        if not obj_id:
            continue
        if was_seen(cursor, obj_id):
            continue

        try:
            price_text = expose.find(class_="aditem-main--middle--price-shipping--price").text.strip()
            price_match = re.search(r"[\d,.]+", price_text)
            price = float(price_match.group().replace(".", "").replace(",", ".")) if price_match else None

            tags = expose.find_all(class_="simpletag")
            size_text = tags[0].text.strip() if tags else ""
            size_match = re.search(r"[\d,.]+", size_text)
            size = float(size_match.group().replace(".", "").replace(",", ".")) if size_match else None

            address_el = expose.find("div", {"class": "aditem-main--top--left"})
            address = " ".join(address_el.text.split()) if address_el else ""
        except Exception:
            continue

        lat, lon = geocode_address(address)
        soup_detail = fetch_html(url)
        images, price_warm = [], None
        if soup_detail:
            for img in soup_detail.find_all("img"):
                src = img.get("src") or ""
                if src.startswith("https://img.kleinanzeigen.de/api/v1/prod-ads/images/"):
                    images.append(src)
                if len(images) >= 5:
                    break
            price_warm = extract_warmmiete_from_soup(soup_detail)

        entry = {
            "id": str(obj_id),
            "url": url,
            "title": title_elem.text.strip(),
            "price": price,
            "price_warm": price_warm,
            "size": size,
            "address": address,
            "lat": lat,
            "lon": lon,
            "swapflat": "tausch" in title_elem.text.lower(),
            "wbs_required": False,
            "photo_url": ",".join(images),
        }
        entries.append(entry)
    return entries

# === Основной процесс ===
def run(url=None):
    conn, cursor = init_db()
    try:
        url = url or BASE_URL
        soup = fetch_html(url)
        if not soup:
            logging.error("❌ Не удалось получить HTML")
            return False

        entries = extract_data(soup)
        if not entries:
            logging.warning("⚠️ Объявления не найдены")
            return False

        new_entries = 0
        for entry in entries:
            if was_seen(cursor, entry["id"]):
                continue
            new_entries += 1
            mark_as_seen(conn, cursor, entry["id"], entry)
            logging.info(f"🏠 {entry['address']} | {entry['price']}€ | {entry['size']} m² | Warmmiete: {entry.get('price_warm')}")
            logging.info(f"   🔗 {entry['url']}")

        if new_entries == 0:
            logging.info("📬 Новых объявлений нет")
        else:
            logging.info(f"✅ Добавлено {new_entries} объявлений")
        return new_entries > 0
    except Exception as e:
        logging.error(f"🔥 Критическая ошибка: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    run()
