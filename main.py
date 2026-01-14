import os
import time
import re
import requests
from bs4 import BeautifulSoup

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SEEN_FILE = "seen.txt"

# URLs de búsqueda (web pública)
# Puedes cambiar filtros después (precio, dormitorios, etc.)
URLS = [
    (
        "Las Condes",
        "https://listado.mercadolibre.cl/inmuebles/casas/arriendo/rm-metropolitana/las-condes/_PriceRange_40CLF-55CLF_NoIndex_True"
    ),
    (
        "Providencia",
        "https://listado.mercadolibre.cl/inmuebles/casas/arriendo/rm-metropolitana/providencia/_PriceRange_40CLF-55CLF_NoIndex_True"
    ),
]


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

def telegram_send(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en Secrets.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()

def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())

def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for x in sorted(seen):
            f.write(x + "\n")

def extract_id_from_url(url: str) -> str:
    # Intenta sacar un identificador estable desde el link
    # Ej: ..._JM#position=...  -> limpiamos anchors/params
    clean = url.split("#")[0].split("?")[0]
    # Usa el path completo como ID si no hay otro
    return clean

def fetch_listings(label: str, url: str):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    # MercadoLibre suele poner links a publicaciones como <a href="...">
    # Tomamos links que parezcan inmuebles y tengan /MLC- o similares.
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        # Filtrado suave: que sea link a item (suele contener /MLC- o /MLC)
        if "mercadolibre.cl" in href and ("MLC-" in href or "/MLC" in href):
            links.append(href)

    # Deduplicar preservando orden
    seen_local = set()
    uniq = []
    for x in links:
        x = x.split("#")[0]
        if x not in seen_local:
            seen_local.add(x)
            uniq.append(x)

    return uniq[:50]  # límite

def main():
    seen = load_seen()
    nuevos = []

    for label, url in URLS:
        links = fetch_listings(label, url)
        for link in links:
            item_id = extract_id_from_url(link)
            if item_id not in seen:
                nuevos.append((label, link))
        time.sleep(1)

    if not nuevos:
        print("0 nuevos. OK.")
        return

    # guardar vistos
    for label, link in nuevos:
        seen.add(extract_id_from_url(link))
    save_seen(seen)

    # Mensaje Telegram (máximo 20 para no saturar)
    msg = [f"Nuevas publicaciones encontradas: {len(nuevos)}\n"]
    for label, link in nuevos[:20]:
        msg.append(f"[{label}] {link}")

    telegram_send("\n".join(msg))
    print("Mensaje enviado.")

if __name__ == "__main__":
    main()
