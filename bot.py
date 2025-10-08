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
@bot.message_handler(commands=['news'])
def send_news(message):
    news = "🗞️ Exemple d'actualité : Bitcoin en hausse de 3% aujourd’hui."
    bot.send_message(message.chat.id, news)

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
