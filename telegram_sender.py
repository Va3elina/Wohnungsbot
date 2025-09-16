# -*- coding: utf-8 -*-
import sqlite3
import math
import requests
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote, quote_plus
from dotenv import load_dotenv

# === Load environment ===
load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_SENDER_TOKEN", "CHANGE_ME")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
TELEGRAM_MEDIA_GROUP_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMediaGroup"
BERLIN_TZ = ZoneInfo("Europe/Berlin")


def calculate_distance(lat1, lon1, lat2, lon2):
    """Вычисление расстояния между координатами (метры)."""
    R = 6371000
    lat1_rad, lon1_rad = math.radians(lat1), math.radians(lon1)
    lat2_rad, lon2_rad = math.radians(lat2), math.radians(lon2)
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def point_in_polygon(lat, lon, polygon):
    """Проверка, входит ли точка в полигон."""
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        lat_i, lon_i = polygon[i]
        lat_j, lon_j = polygon[j]
        if ((lon_i > lon) != (lon_j > lon)):
            slope = (lat_j - lat_i) / (lon_j - lon_i + 1e-15)
            intersect_lat = slope * (lon - lon_i) + lat_i
            if lat < intersect_lat:
                inside = not inside
        j = i
    return inside


def parse_location(location_str):
    """Парсинг строки локации (circle / polygon)."""
    if not location_str:
        return None, None
    if ";" in location_str:
        points = [p.strip() for p in location_str.split(";") if p.strip()]
        polygon = [(float(p.split(",")[0]), float(p.split(",")[1])) for p in points]
        return ("polygon", polygon) if len(polygon) >= 3 else (None, None)
    else:
        parts = location_str.split(",")
        if len(parts) == 3:
            lat, lon, radius = map(lambda x: float(x.strip()), parts)
            return "circle", (lat, lon, radius)
        return None, None


def send_matching_listings():
    """Основная функция отправки новых объявлений."""
    print("📬 Новые объявления найдены! Отправляем пользователям...")
    conn = sqlite3.connect("seen_ids.db")
    cursor = conn.cursor()

    # Метаданные
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS run_metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("SELECT value FROM run_metadata WHERE key = 'last_run'")
    row = cursor.fetchone()
    MIN_CREATED_TIME = datetime.now(BERLIN_TZ) - timedelta(minutes=5) if not row else datetime.fromisoformat(row[0])
    NOW = datetime.now(BERLIN_TZ)
    cursor.execute("INSERT OR REPLACE INTO run_metadata (key, value) VALUES (?, ?)",
                   ('last_run', NOW.isoformat(timespec="seconds")))

    # Отправленные объявления
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_listings (
            user_id INTEGER,
            listing_id TEXT,
            url TEXT,
            sent_at TEXT,
            PRIMARY KEY (user_id, listing_id)
        )
    """)

    # Все новые объявления
    cursor.execute("""
        SELECT id, url, price, price_warm, size, address, lat, lon, created_at, 
               swapflat, wbs_required, source_immoscout, source_kleinanzeigen, 
               source_immowelt, source_inberlinwohnen, photo_url
        FROM listings
        WHERE created_at >= ?
    """, (MIN_CREATED_TIME.isoformat(timespec="seconds"),))
    listings = cursor.fetchall()

    # Пользователи
    cursor.execute("""
        SELECT id, location, min_price, max_price, min_size, max_size, 
               subscribed_until, is_searching,
               tauschwohnung, wbs,
               use_immoscout, use_kleinanzeigen, use_immowelt, use_inberlinwohnen
        FROM users
        WHERE IFNULL(is_searching, 0) = 1
    """)
    users = cursor.fetchall()

    cursor.execute("SELECT user_id, listing_id FROM sent_listings")
    sent_records = set(cursor.fetchall())

    total_sent = 0

    for user in users:
        try:
            (user_id, location, min_price, max_price, min_size, max_size,
             subscribed_until, is_searching,
             tauschwohnung, wbs,
             use_immoscout, use_kleinanzeigen, use_immowelt, use_inberlinwohnen) = user

            # Проверка подписки
            if subscribed_until:
                expiry = datetime.fromisoformat(subscribed_until).replace(tzinfo=BERLIN_TZ)
                if expiry < datetime.now(BERLIN_TZ):
                    cursor.execute("UPDATE users SET is_searching = 0 WHERE id = ?", (user_id,))
                    conn.commit()
                    print(f"[SUBSCRIPTION] 🔕 User {user_id} — подписка истекла, поиск отключён")
                    continue

            loc_type, loc_data = parse_location(location)
            if loc_type is None:
                continue

            if loc_type == "circle":
                lat_u, lon_u, radius_u = loc_data
            else:
                polygon = loc_data

        except Exception as e:
            print(f"[USER ERROR] User {user_id}: {e}")
            continue

        for listing in listings:
            try:
                (listing_id, url, price, price_warm, size, address, lat_l, lon_l,
                 created_at, swapflat, wbs_required,
                 source_immoscout, source_kleinanzeigen, source_immowelt, source_inberlinwohnen,
                 photo_url) = listing

                # Проверка условий
                if (user_id, listing_id) in sent_records:
                    continue
                if None in (price, size, lat_l, lon_l, created_at):
                    continue
                if source_immoscout and not use_immoscout:
                    continue
                if source_kleinanzeigen and not use_kleinanzeigen:
                    continue
                if source_immowelt and not use_immowelt:
                    continue
                if source_inberlinwohnen and not use_inberlinwohnen:
                    continue
                if tauschwohnung == 0 and swapflat == 1:
                    continue
                if wbs == 0 and wbs_required == 1:
                    continue
                if min_price and price < min_price:
                    continue
                if max_price and price > max_price:
                    continue
                if min_size and size < min_size:
                    continue
                if max_size and size > max_size:
                    continue
                if loc_type == "circle" and calculate_distance(lat_u, lon_u, lat_l, lon_l) > radius_u:
                    continue
                if loc_type == "polygon" and not point_in_polygon(lat_l, lon_l, polygon):
                    continue

                # Определяем источник
                if source_immoscout:
                    source_str = "ImmobilienScout24"
                elif source_immowelt:
                    source_str = "Immowelt"
                elif source_kleinanzeigen:
                    source_str = "Kleinanzeigen"
                elif source_inberlinwohnen:
                    source_str = "InBerlinWohnen"
                else:
                    source_str = "Listing"

                address_encoded = quote_plus(address)
                google_maps_url = f"https://www.google.com/maps/search/?api=1&query={address_encoded}"
                url_encoded = quote(url, safe=":/")

                if not price_warm or price_warm == price:
                    price_text = f"💰 <b>Price:</b> {price} €"
                elif price_warm > price:
                    price_text = f"💰 <b>Kaltmiete:</b> {price} € | <b>Warmmiete:</b> {price_warm} €"
                else:
                    price_text = f"💰 <b>Price:</b> {price} €"

                message = (
                    f"🏠 <b>New Flat for You!</b>\n"
                    f"{price_text}\n"
                    f"📏 <b>Size:</b> {size} m²\n"
                    f"🔗 <a href='{url_encoded}'>{source_str} Link</a>\n"
                    f"📍 <a href='{google_maps_url}'>{address}</a>"
                )

                # Отправка фото/сообщения
                photo_urls = [u.strip() for u in (photo_url or '').split(',') if u.strip()]
                if photo_urls:
                    media = []
                    for i, img_url in enumerate(photo_urls[:10]):
                        media.append({
                            "type": "photo",
                            "media": img_url,
                            "caption": message if i == 0 else "",
                            "parse_mode": "HTML"
                        })
                    payload = {"chat_id": user_id, "media": media}
                    response = requests.post(TELEGRAM_MEDIA_GROUP_URL, json=payload)
                else:
                    payload = {"chat_id": user_id, "text": message, "parse_mode": "HTML"}
                    response = requests.post(TELEGRAM_API_URL, json=payload)

                if response.status_code == 200:
                    total_sent += 1
                    cursor.execute(
                        "INSERT INTO sent_listings (user_id, listing_id, url, sent_at) VALUES (?, ?, ?, ?)",
                        (user_id, listing_id, url, datetime.now(BERLIN_TZ).isoformat(timespec="seconds"))
                    )
                    conn.commit()
                else:
                    print(f"❌ Ошибка отправки пользователю {user_id}: {response.status_code}, {response.text}")

            except Exception as e:
                print(f"[ERROR] Внутри цикла listings: {e}")
                continue

    conn.close()
    print(f"[INFO] Завершено: Отправлено {total_sent} новых объявлений.")


def run():
    send_matching_listings()


if __name__ == "__main__":
    run()
