import os
import telebot
from flask import Flask, request
import requests

TOKEN = "8302723677:AAELchM4xbz09DHGFAGmgRuwHBUEoW9tLDw"
CHAT_ID = 1424643628

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running perfectly 🚀"

@app.route(f'/{TOKEN}', methods=['POST'])
def receive_update():
    json_str = request.stream.read().decode('UTF-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

# Exemple : Commande /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "👋 Salut ! Je suis ton bot crypto AiFutur_bot. Tape /news pour les dernières infos.")

# Exemple : Commande /news
import requests
import random

@bot.message_handler(commands=['news'])
def send_news(message):
    try:
        # 1️⃣ On combine crypto + économie mondiale
        sources = [
            "https://min-api.cryptocompare.com/data/v2/news/?lang=EN",
            "https://newsapi.org/v2/top-headlines?country=us&category=business&apiKey=218db5fcb2844e7cac6c91c6158a9b87"
        ]

        crypto_news = requests.get(sources[0]).json()
        eco_news = requests.get(sources[1]).json()

        # 2️⃣ Sélection aléatoire de 2 news crypto + 1 économique
        result = "🗞️ *Dernières nouvelles du marché :*\n\n"

        for i in range(2):
            n = crypto_news["Data"][i]
            result += f"💰 *{n['title']}*\n👉 {n['url']}\n\n"

        for i in range(1):
            n = eco_news["articles"][i]
            result += f"🌍 *{n['title']}*\n👉 {n['url']}\n\n"

        result += "_Actualisé automatiquement via API (CryptoCompare + NewsAPI)_"

        bot.send_message(message.chat.id, result, parse_mode="Markdown")

    except Exception as e:
        bot.send_message(message.chat.id, f"⚠️ Erreur lors de la récupération des news : {e}")

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
