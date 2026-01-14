import os
import time
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# ====== TELEGRAM ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ====== URLs PortalInmobiliario (UF 40–55) ======
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
}

MAX_LINKS_PER_COMUNA = 30
SLEEP_SECONDS = 1


def telegram_send(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()


def extract_links_from_embedded_json(base_url: str, html: str) -> list[str]:
    """
    PortalInmobiliario incluye los avisos en un JSON dentro de un <script>.
    Buscamos ese JSON y extraemos las URLs de las publicaciones.
    """
    soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all("script")
    links = []

    for script in scripts:
        if not script.string:
            continue

        text = script.string.strip()

        # Heurística: el JSON suele contener "listingId" o "canonical_url"
        if "listingId" in text or "canonical_url" in text or "permalink" in text:
            try:
                data = json.loads(text)

                # Buscamos recursivamente URLs
                stack = [data]
                while stack:
                    item = stack.pop()
                    if isinstance(item, dict):
                        for k, v in item.items():
                            if isinstance(v, (dict, list)):
                                stack.append(v)
                            elif isinstance(v, str):
                                if "portalinmobiliario.com" in v and "/arriendo/" in v:
                                    links.append(v)
                    elif isinstance(item, list):
                        stack.extend(item)

            except Exception:
                continue

    # Normalizar y deduplicar
    uniq = []
    seen = set()
    for x in links:
        x = x.split("?")[0].split("#")[0]
        x = urljoin(base_url, x)
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return uniq


def fetch_links(url: str) -> tuple[list[str], str]:
    r = requests.get(url, headers=HEADERS, timeout=30)
    status = r.status_code
    html = r.text
    diag = f"HTTP {status}, html_len={len(html)}"

    if status != 200:
        return [], diag

    links = extract_links_from_embedded_json(url, html)
    return links, diag


def main():
    lines = ["🏠 PortalInmobiliario — Casas en arriendo — UF 40 a UF 55\n"]
    total = 0

    for label, url in URLS:
        try:
            links, diag = fetch_links(url)
            links = links[:MAX_LINKS_PER_COMUNA]

            lines.append(f"📍 {label} — encontrados: {len(links)} ({diag})")
            if not links:
                lines.append("  (No se pudieron extraer links)")
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
