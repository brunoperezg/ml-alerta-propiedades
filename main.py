import os
import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ====== TELEGRAM (GitHub Secrets) ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ====== PORTAL INMOBILIARIO (UF 40–55) ======
URLS = [
    (
        "Las Condes",
        "https://www.portalinmobiliario.com/arriendo/casa/las-condes-metropolitana/_PriceRange_40CLF-55CLF_NoIndex_True",
    ),
    (
        "Providencia",
        "https://www.portalinmobiliario.com/arriendo/casa/providencia-metropolitana/_PriceRange_40CLF-55CLF_NoIndex_True",
    ),
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

MAX_LINKS_PER_COMUNA = 30
SLEEP_SECONDS = 1


def telegram_send(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en GitHub Secrets.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()


def extract_links_portalinmobiliario(base_url: str, html: str) -> list[str]:
    """
    Extrae links de publicaciones desde PortalInmobiliario.
    Tomamos anchors <a href> y filtramos los que parezcan avisos.
    """
    soup = BeautifulSoup(html, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        abs_url = urljoin(base_url, href)
        abs_url = abs_url.split("#")[0]

        # Portal Inmobiliario suele tener avisos con /MLC- o /MLC... en MercadoLibre,
        # pero aquí normalmente son rutas tipo /MLC-... o /<slug>_... en portalinmobiliario.com
        # Filtramos por dominio + que no sea navegación (arriendo/casa/... ya es navegación)
        if "portalinmobiliario.com" in abs_url:
            # Evitar links al mismo listado o filtros
            if "/arriendo/" in abs_url and "/_PriceRange_" in abs_url:
                continue

            # Heurísticas de “aviso”: suele incluir identificadores o path distinto al listado
            # (esto es intencionalmente flexible)
            if re.search(r"/(MLC|PM|inmueble|propiedad|aviso|casa|departamento)", abs_url, re.IGNORECASE) or (
                abs_url.count("/") > 5
            ):
                links.append(abs_url)

    # Deduplicar preservando orden
    seen = set()
    uniq = []
    for x in links:
        x = x.split("?")[0]
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return uniq


def fetch_listing_links(label: str, url: str) -> tuple[list[str], str]:
    r = requests.get(url, headers=HEADERS, timeout=30)
    status = r.status_code
    html = r.text
    diag = f"HTTP {status}, html_len={len(html)}"
    if status != 200:
        return [], diag

    links = extract_links_portalinmobiliario(url, html)
    return links, diag


def main():
    lines = ["🏠 PortalInmobiliario — Casas en arriendo — UF 40 a UF 55\n"]
    total = 0

    for label, url in URLS:
        try:
            links, diag = fetch_listing_links(label, url)
            links = links[:MAX_LINKS_PER_COMUNA]

            lines.append(f"📍 {label} — encontrados: {len(links)} ({diag})")
            if not links:
                lines.append("  (Sin links extraídos)")
            else:
                for link in links:
                    lines.append(f"- {link}")

            total += len(links)
        except Exception as e:
            lines.append(f"📍 {label} — ERROR: {e}")

        lines.append("")
        time.sleep(SLEEP_SECONDS)

    lines.insert(1, f"Total links (mostrados): {total}\n")
    telegram_send("\n".join(lines))
    print(f"Mensaje enviado. Total mostrados: {total}")


if __name__ == "__main__":
    main()
