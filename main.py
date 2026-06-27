import os
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import datetime

# Kunin ang secrets mula sa GitHub
BOT_TOKEN = os.getenv("8646836230:AAHBBuVWxYudopDVsaa3ehAp46WBVcSLZAI")
CHAT_ID = os.getenv("7516609692")

def fetch_odb():
    url = "https://ourdailybread.org/reading"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Kunin ang title at content (I-aadjust kung magbago ang website)
        title = soup.find("h1").get_text(strip=True) if soup.find("h1") else "Daily Bread"
        
        # Hanapin ang main content div (madalas naka-class na 'reading-content' o katulad)
        content_div = soup.find("div", class_="reading-content") or soup.find("article")
        content = content_div.get_text(separator="\n", strip=True) if content_div else "Hindi makuha ang content ngayon."
        
        return f"{title}\n\n{content}"
    except Exception as e:
        return f"Error fetching: {str(e)}"

def translate_text(text):
    try:
        # Hatiin kung mahaba (Google Translate limit is 5000 chars)
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        translator = GoogleTranslator(source='en', target='tl')
        translated = [translator.translate(chunk) for chunk in chunks]
        return "\n\n".join(translated)
    except Exception as e:
        return f"Error translating: {str(e)}"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Hatiin ang message kung sobrang haba (Telegram limit is 4096 chars)
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    
    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload)

if __name__ == "__main__":
    print("Fetching...")
    eng_text = fetch_odb()
    print("Translating...")
    tl_text = translate_text(eng_text)
    
    today = datetime.date.today().strftime("%B %d, %Y")
    final_msg = f"🍞 *Daily Bread (Tagalog)*\n📅 {today}\n\n{tl_text}"
    
    print("Sending to Telegram...")
    send_telegram(final_msg)
    print("Done!")
