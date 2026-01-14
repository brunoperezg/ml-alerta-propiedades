import os
import time
import requests

SITE_ID = os.getenv("SITE_ID", "MLC")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Búsquedas simples por texto (funciona, luego se puede afinar)
QUERIES = [
    ("Las Condes", "arriendo casa Las Condes"),
    ("Providencia", "arriendo casa Providencia"),
]

LIMIT = int(os.getenv("ML_LIMIT", "50"))
CATEGORY = os.getenv("ML_CATEGORY_ID")  # opcional

SEEN_FILE = "seen.txt"


def telegram_send(message: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID.")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message}, timeout=30)
    r.raise_for_status()


def ml_search(q: str):
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/search"
    params = {"q": q, "limit": LIMIT}
    if CATEGORY:
        params["category"] = CATEGORY
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def load_seen() -> set:
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_seen(seen: set) -> None:
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        for item_id in sorted(seen):
            f.write(item_id + "\n")


def format_item(it: dict) -> str:
    return (
        f"- {it.get('title', 'Sin título')}\n"
        f"  Precio: {it.get('price', 'N/A')}\n"
        f"  Link: {it.get('permalink', '')}\n"
    )


def main():
    seen = load_seen()
    nuevos = []
    added_ids = []

    for label, q in QUERIES:
        data = ml_search(q)
        for it in data.get("results", []):
            item_id = it.get("id")
            if not item_id:
                continue
            if item_id not in seen:
                nuevos.append((label, it))
                added_ids.append(item_id)
        time.sleep(1)

    if not nuevos:
        print("0 nuevos. OK.")
        return

    # Guardar vistos
    seen.update(added_ids)
    save_seen(seen)

    # Mensaje Telegram
    mensaje = [f"Nuevas publicaciones encontradas: {len(nuevos)}\n"]
    for label, it in nuevos[:25]:
        mensaje.append(f"[{label}]\n{format_item(it)}")

    telegram_send("\n".join(mensaje))
    print("Mensaje enviado.")


if __name__ == "__main__":
    main()
