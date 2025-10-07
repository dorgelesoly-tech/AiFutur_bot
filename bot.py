import requests
import time
import os
from datetime import datetime

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "8302723677:AAELchM4xbz09DHGFAGmgRuwHBUEoW9tLDw")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1424643628")

# --- ENVOI DE MESSAGE ---
def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

# --- RÉCUPÉRATION DES ACTUALITÉS ---
def get_crypto_news():
    url = "https://cryptopanic.com/api/v1/posts/?auth_token=demo&filter=hot"
    try:
        response = requests.get(url)
        data = response.json()
        news_items = data.get("results", [])[:5]  # les 5 actus principales
        if not news_items:
            return "Aucune actualité disponible pour le moment."
        message = "📰 *Actualités Crypto du Jour* 🪙\n\n"
        for item in news_items:
            title = item.get("title", "Sans titre")
            source = item.get("source", {}).get("title", "")
            message += f"🔹 {title} ({source})\n"
        return message
    except Exception as e:
        return f"Erreur lors du chargement des actus : {e}"

# --- BOUCLE PRINCIPALE ---
def main():
    send_message("🚀 AiFutur Bot en ligne — prêt à t’informer 💡")
    while True:
        now = datetime.utcnow()
        # Envoi à 9h00 GMT chaque jour
        if now.hour == 9 and now.minute == 0:
            news = get_crypto_news()
            send_message(news)
            time.sleep(60)  # éviter d’envoyer deux fois dans la même minute
        time.sleep(20)

if __name__ == "__main__":
    main()
