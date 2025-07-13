import requests

url = "https://www.vwimmobilien.de/_next/data/5vAVnQmMzxYa1cBIF7m9X/wohnen/immobilien-suche/im-herzen-der-steimker-gaerten-mit-blick-auf-den-quartiersplatz-willkommen-im-promenaden-carre.json?slug=wohnen&slug=immobilien-suche&slug=im-herzen-der-steimker-gaerten-mit-blick-auf-den-quartiersplatz-willkommen-im-promenaden-carre"

headers = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

response = requests.get(url, headers=headers)
data = response.json()
props = data["pageProps"]
page_data = props["pageData"]

# Название
title = page_data["title"]["rendered"]

# Адрес
location_slugs = page_data.get("immo_objects_location_slugs", [])
address = ", ".join(location_slugs) if location_slugs else "?"

# Данные по аренде
acf_data = page_data.get("acf", {}).get("object_data_external", {})
rooms = acf_data.get("rooms_count", "?")
size = acf_data.get("size", "?")
cold_rent = acf_data.get("price", "?")
warm_rent = acf_data.get("total_price", "?")
available = acf_data.get("available_date", "k.A.")

# Ссылка
link = page_data.get("link", "нет ссылки")

# Картинки
attachments = page_data.get("attachments", [])
image_urls = [
    "https://www.vwimmobilien.de" + a["url"]
    for a in attachments
    if a.get("format") == "image/jpeg"
]

# Вывод
print("🏠", title)
print("📍", address)
print("📏", rooms, "Zimmer,", size, "m²")
print("💶", f"Kaltmiete: {cold_rent} € / Warmmiete: {warm_rent} €")
print("📅", "Bezugsfrei:", available)
print("🔗", link)
print("🖼️ Bilder:")
for img in image_urls:
    print("   ", img)
