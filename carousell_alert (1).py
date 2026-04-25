import time
import requests
import sqlite3
from bs4 import BeautifulSoup

# ==============================
#   YOUR SETTINGS — EDIT HERE
# ==============================
TELEGRAM_TOKEN   = "8516931943:AAF0wiQrpDrHm95kLSbz5KYHwNVOZZSXI0o"
TELEGRAM_CHAT_ID = "294727152"
SELLER_USERNAME  = "ecoring.id"
CHECK_EVERY      = 120  # check every 2 minutes (in seconds)
# ==============================

SELLER_URL = f"https://id.carousell.com/u/{SELLER_USERNAME}/"
DB_PATH    = "/home/npaskalino/seen_listings.db"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen (
            id TEXT PRIMARY KEY,
            title TEXT,
            price TEXT,
            url TEXT,
            seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn

def is_new(conn, listing_id):
    row = conn.execute(
        "SELECT id FROM seen WHERE id = ?", (listing_id,)
    ).fetchone()
    return row is None

def mark_seen(conn, listing_id, title, price, url):
    conn.execute(
        "INSERT OR IGNORE INTO seen (id, title, price, url) VALUES (?,?,?,?)",
        (listing_id, title, price, url)
    )
    conn.commit()

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=10)
        if not resp.ok:
            print(f"Telegram warning: {resp.text}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_listings():
    listings = []
    try:
        resp = requests.get(SELLER_URL, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            if "/p/" not in href:
                continue

            if href.startswith("http"):
                full_url = href
            else:
                full_url = "https://id.carousell.com" + href

            title_el = a.find("p")
            title = title_el.text.strip() if title_el else "New listing"

            price = ""
            for span in a.find_all("span"):
                text = span.text.strip()
                if "Rp" in text or "$" in text:
                    price = text
                    break

            listing_id = href.split("?")[0]

            if listing_id and listing_id not in [l["id"] for l in listings]:
                listings.append({
                    "id": listing_id,
                    "title": title,
                    "price": price if price else "Check listing",
                    "url": full_url
                })

    except Exception as e:
        print(f"Scraping error: {e}")

    return listings

def run():
    conn = init_db()
    print("=" * 50)
    print("  Carousell Alert Bot is running!")
    print(f"  Watching: {SELLER_URL}")
    print(f"  Checking every {CHECK_EVERY} seconds")
    print("  Press Ctrl+C to stop")
    print("=" * 50)

    send_telegram(
        "✅ <b>Carousell Alert Bot started!</b>\n\n"
        f"Watching: {SELLER_USERNAME}\n"
        f"Checking every {CHECK_EVERY} seconds\n\n"
        "I'll notify you the moment they post something new!"
    )

    print("\nFirst run: loading current listings as baseline...")
    existing = get_listings()
    for listing in existing:
        mark_seen(conn, listing["id"], listing["title"],
                  listing["price"], listing["url"])
    print(f"Found {len(existing)} existing listings. Watching for new ones...\n")

    while True:
        try:
            time.sleep(CHECK_EVERY)
            print("Checking for new listings...")
            listings = get_listings()
            new_count = 0

            for listing in listings:
                if is_new(conn, listing["id"]):
                    print(f"  NEW: {listing['title']} — {listing['price']}")
                    send_telegram(
                        f"🛍️ <b>New listing from {SELLER_USERNAME}!</b>\n\n"
                        f"📦 {listing['title']}\n"
                        f"💰 {listing['price']}\n\n"
                        f"🔗 {listing['url']}"
                    )
                    mark_seen(conn, listing["id"], listing["title"],
                              listing["price"], listing["url"])
                    new_count += 1

            if new_count == 0:
                print("  No new listings.")
            else:
                print(f"  Sent {new_count} alert(s)!")

        except KeyboardInterrupt:
            print("\nBot stopped. Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("Retrying next cycle...")

if __name__ == "__main__":
    run()
