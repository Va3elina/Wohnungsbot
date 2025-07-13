from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import time


def get_datadome_cookie():
    options = Options()
    options.add_argument("--headless=new")  # Запуск без GUI
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--lang=de-DE,de;q=0.9")  # для имитации немецкого клиента

    print("🚀 Запускаем браузер...")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        print("🌐 Переход на https://www.immowelt.de/")
        driver.get("https://www.immowelt.de/")

        time.sleep(6)  # ⏱ Подождем, пока JS отработает и cookie появятся

        print("🔍 Смотрим cookies...")
        cookies = driver.get_cookies()
        for cookie in cookies:
            if cookie["name"] == "datadome":
                print("✅ Найден datadome cookie:")
                print(f"{cookie['name']}={cookie['value']}")
                return cookie["value"]

        print("❌ Cookie datadome не найден.")
    finally:
        driver.quit()


if __name__ == "__main__":
    cookie_value = get_datadome_cookie()
    if cookie_value:
        print("\n📋 Cookie можно вставить в заголовок:")
        print(f"Cookie: datadome={cookie_value}")
# === Запуск напрямую ===
if __name__ == "__main__":
    scraper = ImmoweltScraper()
    scraper.scrape(max_pages=1)

# === Запуск через импорт (в проекте) ===
def run():
    scraper = ImmoweltScraper()
    scraper.scrape(max_pages=1)
    return True