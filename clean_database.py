# -*- coding: utf-8 -*-
import sqlite3
import requests
from datetime import datetime
from time import sleep
from bs4 import BeautifulSoup
import os
import time

DB_PATH = "seen_ids.db"
BATCH_SIZE = 100
STATE_FILE_NULL = "last_checked_id_null.txt"
STATE_FILE_ACTIVE = "last_checked_id_active.txt"
MODE_STATE_FILE = "mode_state.txt"

CLIENT_ID = "ImmobilienScout24-iPhone-Wohnen-AppKey"
CLIENT_SECRET = "pMxNytaNhHPujeeK"

def get_immoscout_token():
    token_url = "https://publicauth.immobilienscout24.de/oauth/token"
    params = {
        "client_id": CLIENT_ID,
        "grant_type": "client_credentials",
        "client_secret": CLIENT_SECRET
    }
    resp = requests.post(token_url, params=params)
    resp.raise_for_status()
    return resp.json().get("access_token")

def immoscout_is_active(data):
    return data.get("header", {}).get("publicationState", "").lower() == "active"

def check_immoscout_listing(obj_id, headers):
    url = f"https://api.mobile.immobilienscout24.de/expose/{obj_id}?adType=RENT"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return "not_found"
        resp.raise_for_status()
        return "active" if immoscout_is_active(resp.json()) else "inactive"
    except:
        return "error"



def check_kleinanzeigen_listing(url):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        print(f"🌍 [clean_db] Проверка Kleinanzeigen: {url}")
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 404:
            return "deleted"
        soup = BeautifulSoup(resp.text, "html.parser")
        spans = soup.find_all('span', class_='pvap-reserved-title')
        for span in spans:
            if 'is-hidden' in span.get('class', []) or 'display:none' in span.get('style', '').replace(' ', ''):
                continue
            txt = span.get_text(strip=True).lower()
            if 'reserviert' in txt: return "reserved"
            if 'gelöscht' in txt: return "deleted"
        return "active"
    except:
        return "error"

def read_mode():
    if not os.path.exists(MODE_STATE_FILE): return "null"
    with open(MODE_STATE_FILE, 'r') as f: return f.read().strip()

def save_mode(mode):
    with open(MODE_STATE_FILE, 'w') as f: f.write(mode)

def get_last_checked_id(mode):
    path = STATE_FILE_NULL if mode == "null" else STATE_FILE_ACTIVE
    try:
        if os.path.exists(path):
            with open(path, 'r') as f: return f.read().strip()
    except Exception as e:
        print(f"⚠️ Не удалось прочитать {path}: {e}")
    return None

def save_last_checked_id(last_id, mode):
    path = STATE_FILE_NULL if mode == "null" else STATE_FILE_ACTIVE
    try:
        with open(path, 'w') as f: f.write(str(last_id))
    except Exception as e:
        print(f"⚠️ Не удалось сохранить {path}: {e}")

def create_tables():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id TEXT PRIMARY KEY,
            url TEXT,
            price REAL,
            size REAL,
            address TEXT,
            lat REAL,
            lon REAL,
            swapflat INTEGER,
            wbs_required INTEGER,
            created_at TEXT,
            source_immoscout INTEGER DEFAULT 0,
            source_kleinanzeigen INTEGER DEFAULT 0,
            is_active INTEGER,
            last_checked TEXT
        )
    """)
    conn.commit()
    conn.close()

def get_next_batch(conn, last_id, is_null_mode):
    cursor = conn.cursor()
    condition = "is_active IS NULL" if is_null_mode else "is_active = 1"
    if last_id:
        cursor.execute(f"""
            SELECT * FROM listings
            WHERE {condition} AND id > ?
            ORDER BY id
            LIMIT ?
        """, (last_id, BATCH_SIZE))
        batch = cursor.fetchall()
        if not batch:
            cursor.execute(f"""
                SELECT * FROM listings
                WHERE {condition}
                ORDER BY id
                LIMIT ?
            """, (BATCH_SIZE,))
            return cursor.fetchall()
        return batch
    else:
        cursor.execute(f"""
            SELECT * FROM listings
            WHERE {condition}
            ORDER BY id
            LIMIT ?
        """, (BATCH_SIZE,))
        return cursor.fetchall()

def run():
    try:
        MAX_RUNTIME = 100
        start_time = time.time()
        create_tables()

        mode = read_mode()
        is_null_mode = mode == "null"
        next_mode = "active" if is_null_mode else "null"

        token = get_immoscout_token()
        immoscout_headers = {
            "Authorization": f"Bearer {token}",
            "User-Agent": "ImmoScout_26.19.3_18.1.1_._",
            "Accept": "application/json",
            "x-is24-device": "iphone",
            "x_is24_client_id": "65E7AE2B87FF46FBB44649D55E68687E"
        }

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        last_id = get_last_checked_id(mode)
        batch = get_next_batch(conn, last_id, is_null_mode)

        if not batch:
            print("🟡 Нет записей — переключаем режим")
            save_mode(next_mode)
            conn.close()
            return

        for row in batch:
            if time.time() - start_time > MAX_RUNTIME:
                print("⏱️ Время вышло — завершаем итерацию")
                break

            checker_type = "kleinanzeigen" if row["source_kleinanzeigen"] else "immoscout" if row["source_immoscout"] else None
            if not checker_type:
                continue

            if checker_type == "immoscout":
                obj_id = int(row['id']) if row['id'].isdigit() else row['id']
                status = check_immoscout_listing(obj_id, immoscout_headers)
            elif checker_type == "kleinanzeigen":
                status = check_kleinanzeigen_listing(row['url'])
            else:
                status = None

            is_active = 1 if status == "active" else 0
            now = datetime.now().isoformat()
            cursor = conn.cursor()

            if is_active == 0:
                cursor.execute("DELETE FROM listings WHERE id = ?", (row['id'],))
            elif is_active == 1:
                cursor.execute("""
                    UPDATE listings SET is_active = ?, last_checked = ?
                    WHERE id = ?
                """, (is_active, now, row['id']))

            conn.commit()
            last_id = row['id']
            sleep(1)

        save_last_checked_id(last_id, mode)
        save_mode(next_mode)
        conn.close()

    except Exception as e:
        print(f"🔥 Ошибка в процессе очистки: {e}")

if __name__ == "__main__":
    print("🧹 Запуск очистки вручную...")
    run()
