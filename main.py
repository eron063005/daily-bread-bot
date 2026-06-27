import os
import requests
import urllib.parse
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import datetime

# ================= CONFIG =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = "https://www.odbm.org"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
# ===========================================

def fetch_todays_devotion_url():
    """Kunin ang link ng TODAY'S devotion gamit ang updated HTML selectors"""
    url = f"{BASE_URL}/en/devotionals"
    
    try:
        print(f"🌐 Fetching: {url}")
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # ✅ Strategy 1: Hanapin ang <div> na may "Today's Devotion", tapos kunin ang parent <a>
        today_label = soup.find("div", string=lambda t: t and "Today's Devotion" in t)
        if today_label:
            link_tag = today_label.find_parent("a", href=True)
            if link_tag and link_tag.get("href"):
                return urllib.parse.urljoin(BASE_URL, link_tag["href"])

        # ✅ Strategy 2: Fallback sa unang link na may "/devotional-category/" (pinakabago sa list)
        first_link = soup.find("a", href=lambda h: h and "/devotional-category/" in h)
        if first_link:
            return urllib.parse.urljoin(BASE_URL, first_link["href"])

        print("❌ Could not find any devotion links in HTML.")
        return None
    except Exception as e:
        print(f"❌ Error fetching URL: {str(e)}")
        return None

def fetch_devotion_content(url):
    """I-scrape ang Title, Scripture, at Devotion Text"""
    try:
        print(f"📥 Fetching content from: {url}")
        res = requests.get(url, headers=HEADERS, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")

        # Title
        title_tag = soup.find("h1") or soup.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "Daily Devotion"

        # Scripture Reference
        scripture = ""
        scripture_btn = soup.find("button", attrs={"aria-label": lambda a: a and ":" in a})
        if scripture_btn:
            scripture = scripture_btn.get_text(strip=True)
        
        # Main Devotion Text (nasa loob ng mga <p> tags sa "Today's Devotion" section)
        content_text = ""
        devotion_header = soup.find("h2", string=lambda t: t and "Today's Devotion" in t)
        if devotion_header:
            # Kunin lahat ng <p> pagkatapos ng header hanggang sa next header o end
            paragraphs = []
            sibling = devotion_header.find_next_sibling("p")
            while sibling:
                if sibling.name == "h2" or sibling.name == "h3":
                    break
                text = sibling.get_text(strip=True)
                if len(text) > 20: # I-filter ang mga short/empty p tags
                    paragraphs.append(text)
                sibling = sibling.find_next_sibling("p")
            content_text = "\n\n".join(paragraphs)
        
        # Fallback kung wala sa specific section
        if not content_text:
            paragraphs = soup.find_all("p")
            content_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30])

        return title, scripture, content_text
    except Exception as e:
        print(f"❌ Content fetch error: {str(e)}")
        return "Error", "", f"Error: {str(e)}"

def translate_text(text):
    """I-translate sa Tagalog (chunked para iwas limit)"""
    if not text: return ""
    try:
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        translator = GoogleTranslator(source='en', target='tl')
        translated = [translator.translate(chunk) for chunk in chunks]
        return "\n\n".join(translated)
    except Exception as e:
        return f"❌ Translation error: {str(e)}"

def send_telegram(message):
    """I-send sa Telegram"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    
    for chunk in chunks:
        payload = {"chat_id": CHAT_ID, "text": chunk}
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            print("✅ Successfully sent to Telegram!")
        else:
            print(f"⚠️ Telegram API Error: {response.text}")

if __name__ == "__main__":
    print("🔍 Finding today's devotion URL...")
    daily_url = fetch_todays_devotion_url()
    
    if not daily_url:
        print("❌ Failed to get URL. Sending fallback message.")
        title, scripture, content = "Error", "", "Hindi makuha ang devotion ngayon. Subukan ulit bukas."
    else:
        print("📥 Scraping content...")
        title, scripture, content = fetch_devotion_content(daily_url)

    print("🌐 Translating to Tagalog...")
    tl_content = translate_text(content)
    
    # Philippine Time (UTC+8)
    today_ph = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%B %d, %Y")
    
    # ✅ EXACT FORMAT NA HINILING MO
    final_msg = (
        f"🍞 Daily Bread (Tagalog)\n"
        f"📅 {today_ph}\n\n"
        f"{title}\n\n"
        f"📖 Scripture:\n{scripture}\n\n"
        f"📝 Devotion:\n{tl_content}"
    )
    
    print("📤 Sending to Telegram...")
    send_telegram(final_msg)
    print("✅ Done!")
