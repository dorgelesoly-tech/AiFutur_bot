# bot.py -- AiFutur Bot (complet)
#  - webhook Flask pour Render
#  - tâches périodiques en threads : news, memecoin detection, binance listing/delisting, daily summary
#  - optional: Twitter alerts (TWITTER_BEARER)
#  - Persist known Binance symbols to local file 'known_binance.json'
#
# IMPORTANT: configure secrets in Render env vars (see README section below)

import os
import time
import json
import threading
import traceback
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests
from flask import Flask, request

import telebot  # pyTelegramBotAPI

# -----------------------------
# Configuration via env vars
# -----------------------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")            # REQUIRED - your bot token
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")        # REQUIRED - your private chat id (as string)
PORT = int(os.getenv("PORT", "5000"))

NEWSAPI_KEY = os.getenv("NEWSAPI_KEY")                  # optional: NewsAPI.org key
TWITTER_BEARER = os.getenv("TWITTER_BEARER")            # optional: X/Twitter API v2 bearer
CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "60"))  # base loop interval
MEMECOIN_CHECK_INTERVAL = int(os.getenv("MEMECOIN_CHECK_INTERVAL", "60")) # seconds
BINANCE_CHECK_INTERVAL = int(os.getenv("BINANCE_CHECK_INTERVAL", "300"))  # seconds
NEWS_CHECK_HOUR_UTC = int(os.getenv("NEWS_CHECK_HOUR_UTC", "9"))          # daily news time (UTC)
DAILY_SUMMARY_HOUR_UTC = int(os.getenv("DAILY_SUMMARY_HOUR_UTC", "8"))    # daily market summary (UTC)

# Files to persist known lists
KNOWN_BINANCE_FILE = "known_binance.json"
KNOWN_MEME_FILE = "known_memes.json"

# Some thresholds (modifiable via env if needed)
MEME_VOLUME_THRESHOLD_USD = float(os.getenv("MEME_VOLUME_THRESHOLD_USD", "15000"))  # minimal 1h volume in USD to consider
MEME_PRICE_CHANGE_H1_THRESHOLD = float(os.getenv("MEME_PRICE_CHANGE_H1_THRESHOLD", "25.0"))  # % change in 1h

# Chains to scan for memecoins (dexscreener uses chain slug names)
CHAINS_TO_SCAN = ["bsc", "eth"]  # bsc = BNB Smart Chain, eth = Ethereum

# Twitter handles to follow (no @)
TWITTER_USERS = os.getenv("TWITTER_USERS", "cz_binance,elonmusk").split(",")

# -----------------------------
# Basic checks
# -----------------------------
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise SystemExit("ERROR: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID must be set as env vars on Render.")

# -----------------------------
# Bot & Flask setup
# -----------------------------
bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
app = Flask(__name__)

# -----------------------------
# Helpers: Telegram send
# -----------------------------
def send_text(text: str):
    """Send a simple message to the configured chat id (markdown disabled for safe rendering)."""
    try:
        bot.send_message(chat_id=str(TELEGRAM_CHAT_ID), text=text)
    except Exception as e:
        print("Telegram send error:", e)
        # try fallback via HTTP
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text})
        except Exception as e2:
            print("Fallback send failed:", e2)

# -----------------------------
# Webhook endpoint for Telegram (Render expects a Flask app)
# -----------------------------
@app.route('/', methods=['GET'])
def index():
    return "AiFutur Bot is running 🚀"

@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def telegram_webhook():
    try:
        json_str = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
    except Exception as e:
        print("Webhook processing error:", e)
    return '', 200

# -----------------------------
# Command handlers
# -----------------------------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    txt = "👋 Salut ! AiFutur Bot actif. Tape /news pour le résumé du jour ou attends le résumé automatique."
    bot.reply_to(message, txt)

@bot.message_handler(commands=['news'])
def cmd_news(message):
    text = build_news_summary_text()
    bot.send_message(message.chat.id, text)

@bot.message_handler(commands=['summary'])
def cmd_summary(message):
    text = build_daily_market_summary()
    bot.send_message(message.chat.id, text)

# Safe ping
@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    bot.reply_to(message, "pong — bot is alive ✅")

# -----------------------------
# News & translation (CryptoCompare + NewsAPI + LibreTranslate)
# -----------------------------
def fetch_crypto_news(limit=3) -> List[Dict[str, Any]]:
    try:
        url = "https://min-api.cryptocompare.com/data/v2/news/?lang=EN"
        r = requests.get(url, timeout=15)
        data = r.json()
        return data.get("Data", [])[:limit]
    except Exception as e:
        print("fetch_crypto_news error:", e)
        return []

def fetch_economic_news(limit=2) -> List[Dict[str, Any]]:
    try:
        if not NEWSAPI_KEY:
            # fallback: use a simple public RSS or dummy
            return [{"title":"Aucune clé NewsAPI — active NEWSAPI_KEY pour des actus économiques","description":""}]
        url = f"https://newsapi.org/v2/top-headlines?country=us&category=business&pageSize={limit}&apiKey={NEWSAPI_KEY}"
        r = requests.get(url, timeout=15)
        data = r.json()
        return data.get("articles", [])[:limit]
    except Exception as e:
        print("fetch_economic_news error:", e)
        return []

def translate_to_fr(text: str) -> str:
    # Use Argos/LibreTranslate endpoint (public instance). If rate-limited, returns original.
    try:
        payload = {"q": text, "source": "en", "target": "fr"}
        r = requests.post("https://translate.argosopentech.com/translate", json=payload, timeout=10)
        j = r.json()
        return j.get("translatedText", text)
    except Exception as e:
        print("translate error:", e)
        return text

def build_news_summary_text() -> str:
    try:
        crypto = fetch_crypto_news(limit=3)
        eco = fetch_economic_news(limit=2)
        parts = []
        parts.append("🧭 Résumé Crypto + Économie (essentiel)\n")
        # Crypto items
        parts.append("💰 Actualités Crypto :")
        for item in crypto:
            title = item.get("title") or item.get("body")[:80]
            body = item.get("body") or item.get("body", "")[:160]
            summary = (body[:220] + "...") if len(body) > 220 else body
            parts.append(f"▫️ {title}\n{summary}\n")
        # Economic items
        parts.append("🌍 Actualités Économiques :")
        for item in eco:
            title = item.get("title", "—")
            desc = item.get("description") or item.get("summary", "")
            parts.append(f"▫️ {title}\n{desc}\n")
        text_en = "\n".join(parts)
        text_fr = translate_to_fr(text_en)
        return text_fr
    except Exception as e:
        print("build_news_summary_text error:", e)
        return "Erreur lors du chargement des news."

# -----------------------------
# Daily market summary (BTC, ETH, top movers)
# -----------------------------
def build_daily_market_summary() -> str:
    try:
        # Basic: fetch BTC & ETH price and 24h change from CoinGecko
        cg = "https://api.coingecko.com/api/v3/simple/price"
        params = {"ids":"bitcoin,ethereum","vs_currencies":"usd","include_24hr_change":"true"}
        r = requests.get(cg, params=params, timeout=10).json()
        btc = r.get("bitcoin", {})
        eth = r.get("ethereum", {})
        text = f"📊 Résumé quotidien ({datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')})\n"
        text += f"• BTC : ${btc.get('usd', '?')} ({btc.get('usd_24h_change', 0):+.2f}%)\n"
        text += f"• ETH : ${eth.get('usd', '?')} ({eth.get('usd_24h_change', 0):+.2f}%)\n\n"
        # top movers (CoinGecko simple market data)
        movers = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
        text += "🔝 Tendances (trending):\n"
        coins = movers.get("coins", [])[:3]
        for c in coins:
            item = c.get("item", {})
            text += f"• {item.get('name')} ({item.get('symbol')})\n"
        return text
    except Exception as e:
        print("daily summary error:", e)
        return "Erreur résumé quotidien."

# -----------------------------
# Binance listing / delisting detection
# -----------------------------
def load_known_binance() -> Dict[str, Any]:
    try:
        if os.path.exists(KNOWN_BINANCE_FILE):
            with open(KNOWN_BINANCE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {"symbols": []}

def save_known_binance(data: Dict[str, Any]):
    try:
        with open(KNOWN_BINANCE_FILE, "w") as f:
            json.dump(data, f)
    except Exception as e:
        print("save_known_binance error:", e)

def fetch_binance_symbols() -> List[str]:
    try:
        r = requests.get("https://api.binance.com/api/v3/exchangeInfo", timeout=15)
        data = r.json()
        symbols = [s["symbol"] for s in data.get("symbols", [])]
        return symbols
    except Exception as e:
        print("fetch_binance_symbols error:", e)
        return []

def check_binance_listings_and_delistings():
    try:
        known = load_known_binance()
        known_set = set(known.get("symbols", []))
        current = set(fetch_binance_symbols())
        added = current - known_set
        removed = known_set - current
        if added:
            for s in sorted(added):
                send_text(f"🚀 Nouvelle paire LISTÉE sur Binance : {s}\n(Prépare-toi, surveille le marché autour de ce token)")
        if removed:
            for s in sorted(removed):
                send_text(f"⚠️ SUPPRESSION / DELIST sur Binance détectée : {s}\nVérifie sur Binance pour confirmation.")
        # persist current
        save_known_binance({"symbols": sorted(list(current))})
    except Exception as e:
        print("check_binance_listings_and_delistings error:", e)

# -----------------------------
# Memecoin detection via Dexscreener
# -----------------------------
def check_memecoins_once():
    try:
        alerts = []
        for chain in CHAINS_TO_SCAN:
            # Dexscreener API: fetch recently added pairs or tokens by chain.
            # We try the "pairs" endpoint which returns active pairs.
            url = f"https://api.dexscreener.com/latest/dex/search/?q=&chain={chain}"
            # Note: Dexscreener free API semantics change; this is a best-effort call
            r = requests.get(url, timeout=12)
            if r.status_code != 200:
                continue
            data = r.json()
            # `data` may contain `pairs` or `tokens` depending on endpoint; handle generically
            # We'll scan returned lists for big 1h changes and volume
            items = []
            if isinstance(data, dict):
                # try multiple keys
                for k in ("pairs", "tokens", "results"):
                    if k in data and isinstance(data[k], list):
                        items = data[k]
                        break
                # sometimes data is a list
                if not items and isinstance(data.get("pairs"), list):
                    items = data["pairs"]
            if not items and isinstance(data, list):
                items = data
            # iterate
            for it in items[:80]:
                try:
                    # structure varies; attempt safe extraction
                    # p keys: 'baseToken' or 'token'
                    base = it.get("baseToken") or it.get("token") or {}
                    symbol = base.get("symbol") or it.get("symbol") or base.get("name") or "UNKNOWN"
                    # price change 1h maybe nested
                    price_change_h1 = 0.0
                    vol_h1 = 0.0
                    # Dexscreener pair shape:
                    price_change_h1 = float(it.get("priceChange", {}).get("h1", 0) or 0)
                    vol_h1 = float(it.get("volume", {}).get("h1", 0) or 0)
                    # fallback extraction
                    if price_change_h1 == 0 and "priceChange" in it and isinstance(it["priceChange"], (float,int)):
                        price_change_h1 = float(it["priceChange"])
                    # filter
                    if abs(price_change_h1) >= MEME_PRICE_CHANGE_H1_THRESHOLD and vol_h1 >= MEME_VOLUME_THRESHOLD_USD:
                        chain_readable = chain.upper()
                        alerts.append(f"🚨 {symbol} ({chain_readable}) {price_change_h1:+.1f}% (1h) • vol1h=${int(vol_h1)}")
                except Exception:
                    continue
        if alerts:
            msg = "🐸 *ALERTE MEMECOIN*\n" + "\n".join(alerts)
            send_text(msg)
    except Exception as e:
        print("check_memecoins_once error:", e)
        traceback.print_exc()

# -----------------------------
# Twitter scanning (optional)
# -----------------------------
def twitter_recent_tweets_for_user(username: str, since_id=None):
    try:
        if not TWITTER_BEARER:
            return []
        # get user id
        headers = {"Authorization": f"Bearer {TWITTER_BEARER}"}
        u = requests.get(f"https://api.twitter.com/2/users/by/username/{username}", headers=headers, timeout=10)
        if u.status_code != 200:
            return []
        uid = u.json().get("data", {}).get("id")
        if not uid:
            return []
        params = {"max_results": 5, "tweet.fields":"created_at,text"}
        t = requests.get(f"https://api.twitter.com/2/users/{uid}/tweets", headers=headers, params=params, timeout=10)
        if t.status_code != 200:
            return []
        data = t.json().get("data", []) or []
        return data
    except Exception as e:
        print("twitter_recent_tweets_for_user error:", e)
        return []

def check_twitter_alerts():
    try:
        if not TWITTER_BEARER:
            return
        for handle in TWITTER_USERS:
            handle = handle.strip()
            tweets = twitter_recent_tweets_for_user(handle)
            for tw in tweets:
                text = tw.get("text", "")
                # simple keyword heuristic
                keywords = ["binance", "list", "launch", "airdrop", "mint", "pump"]
                if any(k in text.lower() for k in keywords):
                    send_text(f"🐦 Tweet important @{handle} : {text[:300]}")
    except Exception as e:
        print("check_twitter_alerts error:", e)

# -----------------------------
# Scheduler & threads
# -----------------------------
def scheduler_loop():
    # Persist known binance on first run if not exist
    if not os.path.exists(KNOWN_BINANCE_FILE):
        symbols = fetch_binance_symbols()
        save_known_binance({"symbols": sorted(list(symbols))})
    last_daily_news_date = None
    last_daily_summary_date = None

    while True:
        try:
            now = datetime.utcnow()
            # frequent tasks
            check_memecoins_once()   # memecoin scanner (every loop)
            check_twitter_alerts()   # optional, light
            # check binance listings on longer interval
            # we run the heavy check every BINANCE_CHECK_INTERVAL seconds using loop time
            time.sleep(1)
            # instead of precise timers in this simple loop, we schedule by checking timestamps
            # to keep it readable we use sleep in the main while; we call heavy checks conditionally below
            break
        except Exception as e:
            print("scheduler loop error:", e)
            time.sleep(5)

def periodic_worker():
    # This worker does periodic heavy-lifting on separate timed intervals.
    next_binance = 0
    next_news = 0
    next_summary = 0
    next_memes = 0
    next_twitter = 0
    while True:
        now_ts = time.time()
        try:
            if now_ts >= next_memes:
                check_memecoins_once()
                next_memes = now_ts + max(30, MEMECOIN_CHECK_INTERVAL)  # every MEMECOIN_CHECK_INTERVAL seconds

            if now_ts >= next_binance:
                check_binance_listings_and_delistings()
                next_binance = now_ts + BINANCE_CHECK_INTERVAL

            # daily news at NEWS_CHECK_HOUR_UTC
            utc_now = datetime.utcnow()
            if utc_now.hour == NEWS_CHECK_HOUR_UTC and (now_ts >= next_news):
                try:
                    n_text = build_news_summary_text()
                    send_text("📰 Résumé quotidien :\n" + n_text)
                except Exception as e:
                    print("daily news send error:", e)
                next_news = now_ts + 60*60*22  # avoid re-sending for that same hour

            # daily market summary
            if utc_now.hour == DAILY_SUMMARY_HOUR_UTC and (now_ts >= next_summary):
                try:
                    s = build_daily_market_summary()
                    send_text("📈 Résumé quotidien marché :\n" + s)
                except Exception as e:
                    print("daily summary send error:", e)
                next_summary = now_ts + 60*60*22

            # twitter (small)
            if TWITTER_BEARER and now_ts >= next_twitter:
                check_twitter_alerts()
                next_twitter = now_ts + 180

            time.sleep(1)
        except Exception as e:
            print("periodic_worker error:", e)
            time.sleep(5)

# -----------------------------
# Entrypoint
# -----------------------------
def start_workers():
    # start periodic worker thread
    t = threading.Thread(target=periodic_worker, daemon=True)
    t.start()

# start workers on import
start_workers()

# -----------------------------
# Start Flask app (Render will run this as a web process)
# -----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", PORT))
    print(f"Starting AiFutur Bot - webhook listening on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port)
