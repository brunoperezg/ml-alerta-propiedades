import os
import time
import requests
from bs4 import BeautifulSoup

# ====== TELEGRAM (se configuran en GitHub Secrets) ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ====== URLs filtradas (UF 40–55) ======
URLS = [
    (
        "Las Condes",
        "https://listado.mercadolibre.cl/inmuebles/casas/arriendo/rm-metropolitana/las-condes/_PriceRange_40CLF-55CLF_NoIndex_True",
    ),
    (
        "Providencia",
        "https://listado.mercadolibre.cl/inmuebles/casas/arriendo/rm-metropolitana/providencia/_PriceRange_40CLF-55CLF_NoIndex_True",
    ),
]

# Headers básicos para que el request parezca navegador
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
}

MAX_LINKS_PER_COMUNA = 30  # evita mensajes enormes
SLEEP_SECONDS = 1


def telegram_send(message: str) -> None:
    """Envía un mensaje a Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en GitHub Secrets.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()


def fetch_listing_links(url: str) -> list[str]:
    """
    Descarga el HTML del listado y extrae links a publicaciones.
    Devuelve una lista de URLs (deduplicada, preservando orden).
    """
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Links de publicaciones suelen contener MLC- (Chile)
        if "mercadolibre.cl" in href and ("MLC-" in href or "/MLC" in href):
            clean = href.split("#")[0]
            links.append(clean)

    # Deduplicar preservando orden
    seen = set()
    uniq = []
    for x in links:
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return uniq


def main():
    # Construimos el mensaje en 2 bloques (Las Condes / Providencia)
    lines = ["🏠 Casas en arriendo — UF 40 a UF 55\n"]

    total_links = 0

    for label, url in URLS:
        try:
            links = fetch_listing_links(url)
            # recortamos por comuna para no saturar
            links = links[:MAX_LINKS_PER_COMUNA]

            lines.append(f"📍 {label} — mostrando {len(links)}")
            if not links:
                lines.append("  (Sin resultados)")
            else:
                for link in links:
                    lines.append(f"- {link}")

            total_links += len(links)
        except Exception as e:
            lines.append(f"📍 {label} — ERROR al consultar listado: {e}")

        lines.append("")  # línea en
