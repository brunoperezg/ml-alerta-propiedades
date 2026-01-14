import os
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ====== TELEGRAM (GitHub Secrets) ======
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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

MAX_LINKS_PER_COMUNA = 30
SLEEP_SECONDS = 1

# patrones típicos de links de items en Mercado Libre Chile
ITEM_PATTERNS = [
    re.compile(r"/MLC-\d+"),          # /MLC-123456789
    re.compile(r"MLC-\d+"),           # MLC-123456789 (en cualquier parte)
]


def telegram_send(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en GitHub Secrets.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()


def looks_blocked(html: str) -> bool:
    """Heurística simple de bloqueo/anti-bot."""
    h = html.lower()
    keywords = [
        "captcha", "robot", "no eres un robot", "verifica", "blocked", "access denied",
        "perimeterx", "px-captcha", "challenge", "unusual traffic"
    ]
    return any(k in h for k in keywords)


def extract_links_from_html(base_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")

    # 1) Primero: links directos típicos del listado (más confiable)
    # Muchos listados usan anchors con clases específicas.
    # Tomamos todos los <a href> y filtramos por patrón.
    raw_hrefs = []
    for a in soup.find_all("a", href=True):
        raw_hrefs.append(a["href"])

    # 2) Normalizar (absolutos) + filtrar por patrones de item
    links = []
    for href in raw_hrefs:
        abs_url = urljoin(base_url, href)
        abs_url = abs_url.split("#")[0]

        if any(p.search(abs_url) for p in ITEM_PATTERNS):
            links.append(abs_url)

    # 3) Si no encontramos nada, intentamos un fallback:
    # buscar strings "MLC-123..." en el HTML y reconstruir links
    if not links:
        ids = set(re.findall(r"MLC-\d+", html))
        for item_id in list(ids)[:200]:
            links.append(f"https://articulo.mercadolibre.cl/{item_id}")

    # Deduplicar preservando orden
    seen = set()
    uniq = []
    for x in links:
        x = x.split("?")[0]  # limpia tracking
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return uniq


def fetch_listing_links(url: str) -> tuple[list[str], str]:
    """
    Devuelve (links, diagnostico_texto).
    diagnostico_texto se usa para entender por qué a veces hay 0 resultados.
    """
    r = requests.get(url, headers=HEADERS, timeout=30)
    status = r.status_code
    html = r.text

    diag = f"HTTP {status}, html_len={len(html)}"

    if status != 200:
        return [], f"{diag} (no 200)"

    if looks_blocked(html):
        return [], f"{diag} (posible bloqueo/anti-bot detectado)"

    links = extract_links_from_html(url, html)
    return links, diag


def main():
    lines = ["🏠 Casas en arriendo — UF 40 a UF 55\n"]
    total_links = 0

    for label, url in URLS:
        try:
            links, diag = fetch_listing_links(url)
            links = links[:MAX_LINKS_PER_COMUNA]

            lines.append(f"📍 {label} — encontrados: {len(links)}  ({diag})")
            if not links:
                lines.append("  (Sin links extraídos. Si esto pasa siempre, es bloqueo o cambió el HTML.)")
            else:
                for link in links:
                    lines.append(f"- {link}")

            total_links += len(links)

        except Exception as e:
            lines.append(f"📍 {label} — ERROR: {e}")

        lines.append("")
        time.sleep(SLEEP_SECONDS)

    lines.insert(1, f"Total links (mostrados): {total_links}\n")
    telegram_send("\n".join(lines))
    print(f"Mensaje enviado. Total mostrados: {total_links}")


if __name__ == "__main__":
    main()
