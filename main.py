import os
import time
import requests
from bs4 import BeautifulSoup

# ====== TELEGRAM (se configuran en GitHub Secrets) ======
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ====== URLs filtradas (Publicados hoy) ======
URLS = [
    (
        "Las Condes",
        "https://listado.mercadolibre.cl/inmuebles/casas/arriendo/rm-metropolitana/las-condes/_PublishedToday_YES_NoIndex_True",
    ),
    (
        "Providencia",
        "https://listado.mercadolibre.cl/inmuebles/casas/arriendo/rm-metropolitana/providencia/_PublishedToday_YES_NoIndex_True",
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


def telegram_send(message: str) -> None:
    """Envía un mensaje a Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en GitHub Secrets.")

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()


def fetch_listings(label: str, url: str) -> list[str]:
    """
    Descarga el HTML del listado y extrae links a publicaciones.
    Devuelve una lista de URLs (máximo 80).
    """
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]

        # Normalmente los links de publicaciones en MercadoLibre contienen MLC-
        # Ajuste suave (no demasiado estricto para tolerar cambios de HTML)
        if "mercadolibre.cl" in href and ("MLC-" in href or "/MLC" in href):
            # quitar fragmentos (#...) para que quede limpio
            clean = href.split("#")[0]
            links.append(clean)

    # Deduplicar preservando orden
    seen = set()
    uniq = []
    for x in links:
        if x not in seen:
            seen.add(x)
            uniq.append(x)

    return uniq[:80]


def main():
    resultados = []

    for label, url in URLS:
        try:
            links = fetch_listings(label, url)
            for link in links:
                resultados.append((label, link))
        except Exception as e:
            # Si falla una comuna, seguimos con la otra
            resultados.append((label, f"ERROR al consultar listado: {e}"))
        time.sleep(1)

    # Siempre enviamos algo
    if not resultados:
        telegram_send("Hoy no hay publicaciones (Publicados hoy) para Las Condes / Providencia.")
        print("Enviado: 0 resultados.")
        return

    # Armar mensaje (máximo 30 líneas para no saturar Telegram)
    msg = [f"📌 Publicados HOY — resultados: {len(resultados)}\n"]
    count_links = 0

    for label, link in resultados:
        # si es un error, igual lo mostramos
        if link.startswith("ERROR"):
            msg.append(f"[{label}] {link}")
            continue

        msg.append(f"[{label}] {link}")
        count_links += 1
        if count_links >= 30:
            break

    telegram_send("\n".join(msg))
    print(f"Enviado: {len(resultados)} resultados (mostrando hasta 30).")


if __name__ == "__main__":
    main()
