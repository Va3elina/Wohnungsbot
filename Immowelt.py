# -*- coding: utf-8 -*-
import requests
import time
import logging
import sqlite3
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

# === Загрузка .env ===
load_dotenv()

# === Настройка логирования ===
LOG_FILE = os.getenv("LOG_FILE", "immowelt_scraper.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# === Константы ===
BERLIN_TZ = ZoneInfo("Europe/Berlin")
DB_FILE = os.getenv("DB_FILE", "seen_ids.db")

# === Вспомогательные функции ===
def init_db():
    """Создаёт БД и таблицу listings при необходимости"""
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
    """Проверяет, есть ли объект с таким id в базе"""
    cursor.execute("SELECT 1 FROM listings WHERE id = ?", (obj_id,))
    return cursor.fetchone() is not None


def mark_as_seen(conn, cursor, obj_id: str, listing: dict):
    """Сохраняет объявление в базу"""
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
        0,  # source_kleinanzeigen
        1,  # source_immowelt
        listing["photo_url"],
        "1",
        datetime.now(BERLIN_TZ).isoformat(timespec="seconds"),
        0,  # source_wggesucht
        0   # source_inberlinwohnen
    ))
    conn.commit()


def clean_price_size(value: str):
    """Парсинг цены/площади из строки"""
    if not value:
        return None
    val = value.replace("\xa0", "").replace("€", "").replace("m²", "").strip()
    val = val.replace(".", "").replace(",", ".")
    try:
        return float(val)
    except ValueError:
        return None


# === Класс парсера Immowelt ===
class ImmoweltScraper:
    def __init__(self):
        """Создаёт сессию и заголовки"""
        self.session = requests.Session()
        proxy = os.getenv("IMMO_PROXY")
        if proxy:
            self.session.proxies = {"http": proxy, "https": proxy}

        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Accept-Language": "de-DE,de;q=0.9",
            "Referer": "https://www.immowelt.de/",
            "Origin": "https://www.immowelt.de"
        }
        self.datadome_cookie = None

    def bypass_datadome(self) -> bool:
        """Пробует обойти защиту DataDome (placeholders вместо секретов)"""
        logging.info("Пытаемся обойти защиту DataDome...")
        url = "https://dd.immowelt.de/js/"
        headers = self.headers.copy()
        headers.update({
            "content-type": "application/x-www-form-urlencoded",
            "referer": "https://www.immowelt.de/",
        })
        data = {
            "jspl": os.getenv("DATADOME_JSPL", "CHANGE_ME"),
            "cid": os.getenv("DATADOME_CID", "CHANGE_ME"),
            "ddk": os.getenv("DATADOME_DDK", "CHANGE_ME"),
            "request": "%2Fclassified-search%3FdistributionTypes%3DRent",
            "responsePage": "origin",
            "ddv": "5.1.2",
        }
        try:
            response = self.session.post(url, headers=headers, data=data)
            self.datadome_cookie = response.json().get("cookie", "").split(";")[0]
            if self.datadome_cookie:
                logging.info("✅ DataDome cookie установлен")
                return True
        except Exception as e:
            logging.error(f"❌ Ошибка обхода DataDome: {e}")
        return False

    def search_listings(self, page=1, size=30):
        """Ищет список объявлений"""
        url = "https://www.immowelt.de/serp-bff/search"
        payload = {
            "criteria": {
                "distributionTypes": ["Rent"],
                "estateTypes": ["House", "Apartment"],
                "location": {"placeIds": ["AD02DE1"]},
                "projectTypes": ["New_Build", "Stock"]
            },
            "paging": {"page": page, "size": size, "order": "DateDesc"}
        }
        headers = self.headers.copy()
        headers["Content-Type"] = "application/json; charset=utf-8"
        if self.datadome_cookie:
            headers["Cookie"] = self.datadome_cookie
        r = self.session.post(url, headers=headers, json=payload)
        if r.status_code == 200:
            return r.json()
        logging.warning(f"⚠️ Не удалось получить страницу {page}")
        return None

    def get_listing_details(self, listing_ids):
        """Подробности по объявлениям"""
        if not listing_ids:
            return []
        url = f"https://www.immowelt.de/classifiedList/{','.join(listing_ids)}"
        headers = self.headers.copy()
        headers["x-language"] = "de"
        if self.datadome_cookie:
            headers["Cookie"] = self.datadome_cookie
        r = self.session.get(url, headers=headers)
        return r.json() if r.status_code == 200 else []

    def parse_and_store_listing(self, listing, conn, cursor):
        """Парсит объявление и сохраняет в базу"""
        obj_id = listing.get("id")
        if not obj_id or was_seen(cursor, obj_id):
            return

        address_parts = listing.get("location", {}).get("address", {})
        address = ", ".join(filter(None, [
            address_parts.get("street"),
            address_parts.get("zipCode"),
            address_parts.get("city")
        ]))

        coords = listing.get("location", {}).get("coordinates", {})
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        price = clean_price_size(listing.get("hardFacts", {}).get("price", {}).get("value"))

        size = None
        for fact in listing.get("hardFacts", {}).get("facts", []):
            if fact.get("type") == "livingSpace":
                size = clean_price_size(fact.get("value"))

        photo_url = None
        images = listing.get("gallery", {}).get("images", [])
        if images:
            photo_url = images[0].get("url")

        url = listing.get("url") or f"https://www.immowelt.de/expose/{listing.get('metadata', {}).get('legacyId')}"

        parsed = {
            "url": url,
            "price": price,
            "price_warm": None,
            "size": size,
            "address": address,
            "lat": lat,
            "lon": lon,
            "photo_url": photo_url,
            "swapflat": 0,
            "wbs_required": 0
        }

        mark_as_seen(conn, cursor, obj_id, parsed)
        logging.info(f"💾 Сохранено объявление: {obj_id}")

    def scrape(self, max_pages=1):
        """Основной процесс скрапинга"""
        if not self.bypass_datadome():
            return
        conn, cursor = init_db()
        for page in range(1, max_pages + 1):
            result = self.search_listings(page=page)
            if not result:
                continue
            ids = [item["id"] for item in result.get("classifieds", [])]
            details = self.get_listing_details(ids)
            for listing in details:
                try:
                    self.parse_and_store_listing(listing, conn, cursor)
                except Exception as e:
                    logging.warning(f"⚠️ Ошибка при обработке: {e}")
            time.sleep(1.5)
        conn.close()


# === Запуск напрямую ===
if __name__ == "__main__":
    scraper = ImmoweltScraper()
    scraper.scrape(max_pages=1)


# === Запуск через импорт (в проекте) ===
def run():
    scraper = ImmoweltScraper()
    scraper.scrape(max_pages=1)
    return True
