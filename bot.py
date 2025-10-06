import requests
import time
import os

# --- CONFIGURATION ---
TOKEN = os.getenv("TELEGRAM_TOKEN", "8302723677:AAELchM4xbz09DHGFAGmgRuwHBUEoW9tLDw")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1424643628")

# --- FONCTION D’ENVOI DE MESSAGE ---
def send_message(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    requests.post(url, data=data)

# --- FONCTION PRINCIPALE ---
def main():
    send_message("🚀 Le bot AiFutur est en ligne !")
    while True:
        try:
            # Exemple de message automatisé
            send_message("📰 Actualités crypto du jour : marché calme mais BTC reste fort 💪")
            time.sleep(3600)  # Attendre 1 heure avant le prochain message
        except Exception as e:
            print("Erreur :", e)
            time.sleep(60)

if __name__ == "__main__":
    main()
