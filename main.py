import os
import time
import requests
import psycopg2
from psycopg2.extras import execute_values

SITE_ID = os.getenv("SITE_ID", "MLC")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Búsquedas simples por texto
QUERIES = [
    ("Las Condes", "arriendo casa Las Condes"),
    ("Providencia", "arriendo casa Providencia"),
]

LIMIT = int(os.getenv("ML_LIMIT", "50"))
CATEGORY = os.getenv("ML_CATEGORY_ID")  # opcional

DATABASE_URL = os.getenv("DATABASE_URL")


def telegram_send(message: str) -> None:
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    r = requests.post(
        url,
        json={"chat_id": TELEGRAM_CHAT_ID, "text": message},
        timeout=30
    )
    r.raise_for_status()


def db_connect():
    return psycopg2.connect(DATABASE_URL)


def db_init(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (
                item_id TEXT PRIMARY KEY,
                first_seen_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()


def already_seen(conn, item_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("SELECT 1 FROM seen_items WHERE item_id = %s", (item_id,))
        return cur.fetchone() is not None


def mark_seen_bulk(conn, item_ids):
    rows = [(i,) for i in item_ids]
    with conn.cursor() as cur:
        execute_values(
            cur,
            "INSERT INTO seen_items(item_id) VALUES %s ON CONFLICT DO NOTHING",
            rows
        )
    conn.commit()


def ml_search(q: str):
    url = f"https://api.mercadolibre.com/sites/{SITE_ID}/search"
    params = {"q": q, "limit": LIMIT}
    if CATEGORY:
        params["category"] = CATEGORY
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def format_item(it: dict) -> str:
    return (
        f"- {it.get('title', 'Sin título')}\n"
        f"  Precio: {it.get('price', 'N/A')}\n"
        f"  Link: {it.get('permalink', '')}\n"
    )


def main():
    conn = db_connect()
    db_init(conn)

    nuevos = []

    for label, q in QUERIES:
        data = ml_search(q)
        for it in data.get("results", []):
            item_id = it.get("id")
            if not item_id:
                continue
            if not already_seen(conn, item_id):
                nuevos.append((label, it))
        time.sleep(1)

    if not nuevos:
        print("0 nuevos. OK.")
        return

    mark_seen_bulk(conn, [it["id"] for _, it in nuevos])

    mensaje = [f"Nuevas propiedades encontradas: {len(nuevos)}\n"]
    for label, it in nuevos[:25]:
        mensaje.append(f"[{label}]\n{format_item(it)}")

    telegram_send("\n".join(mensaje))
    print("Mensaje enviado.")


if __name__ == "__main__":
    main()
