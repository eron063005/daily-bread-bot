import os
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import datetime
import re

# ================= CONFIG =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = "https://www.odbm.org"
# ===========================================

def fetch_todays_devotion_url():
    """Pumunta sa main devotionals page at kunin ang link ng TODAY'S devotion"""
    url = f"{BASE_URL}/en/devotionals"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Hanapin ang "Today's Devotion" section at ang "Read Today's Devotion" link
        # Common pattern: ang first devotional card ay usually ang today's
        today_link = soup.find("a", string=lambda text: text and "Read Today's Devotion" in text)
        
        if today_link and today_link.get("href"):
            daily_url = today_link["href"]
            # Kung relative URL, gawing absolute
            if daily_url.startswith("/"):
                daily_url = BASE_URL + daily_url
            return daily_url
        else:
            # Fallback: kunin ang first devotional link sa list
            first_devotional = soup.find("div", class_="devotional-card") or soup.find("article")
            if first_devotional:
                link_tag = first_devotional.find("a")
                if link_tag and link_tag.get("href"):
                    daily_url = link_tag["href"]
                    if daily_url.startswith("/"):
                        daily_url = BASE_URL + daily_url
                    return daily_url
            return None
    except Exception as e:
        print(f"❌ Error fetching today's URL: {str(e)}")
        return None

def fetch_devotion_content(url):
    """I-scrape ang actual content ng daily devotion page"""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Kunin ang title (usually h1)
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Daily Devotion"
        
        # Kunin ang scripture (karaniwang nasa h2 na may "Scripture" o nasa separate div)
        scripture = ""
        scripture_section = soup.find(string=lambda text: text and "Today's Scripture" in text)
        if scripture_section:
            scripture_tag = scripture_section.find_next_sibling() or scripture_section.parent.find_next()
            scripture = scripture_tag.get_text(strip=True) if scripture_tag else ""
        
        # Kunin ang main devotion content
        content = ""
        # Try common class names for content
        content_div = (soup.find("div", class_="devotion-content") or 
                      soup.find("div", class_="article-body") or
                      soup.find("article") or
                      soup.find("div", attrs={"itemprop": "articleBody"}))
        
        if content_div:
            # Tanggalin ang mga script, style, at extra elements
            for tag in content_div(["script", "style", "nav", "footer"]):
                tag.decompose()
            content = content_div.get_text(separator="\n", strip=True)
        
        # Kung walang nakuha sa content_div, subukang kunin lahat ng paragraphs
        if not content or len(content) < 50:
            paragraphs = soup.find_all("p")
            content = "\n\n".join([p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20])
        
        full_text = f"{title}\n\n📖 Scripture:\n{scripture}\n\n📝 Devotion:\n{content}"
        return full_text
    except Exception as e:
        return f"❌ Error fetching content: {str(e)}"

def translate_text(text):
    try:
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        translator = GoogleTranslator(source='en', target='tl')
        translated = [translator.translate(chunk) for chunk in chunks]
        return "\n\n".join(translated)
    except Exception as e:
        return f"❌ Translation error: {str(e)}"

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    # Hatiin kung mahaba (Telegram limit: 4096 chars)
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    
    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, json=payload, timeout=30)
        
        # === DEBUG LOGGING PARA SA TELEGRAM ===
        print(f"📡 Telegram Status Code: {response.status_code}")
        print(f"📡 Telegram Response: {response.text}")
        
        if response.status_code != 200:
            print(f"⚠️ Telegram API Error: {response.json()}")

if __name__ == "__main__":
    print("🔍 Finding today's devotion URL...")
    daily_url = fetch_todays_devotion_url()
    
    if not daily_url:
        print("❌ Could not find today's devotion URL. Using fallback message.")
        eng_text = "Sorry, hindi makuha ang today's devotion. Subukan ulit bukas."
    else:
        print(f"📄 Found URL: {daily_url}")
        print("📥 Fetching content...")
        eng_text = fetch_devotion_content(daily_url)
    
    print("🌐 Translating to Tagalog...")
    tl_text = translate_text(eng_text)
    
    today = datetime.date.today().strftime("%B %d, %Y")
    final_msg = f"🍞 *Daily Bread (Tagalog)*\n📅 {today}\n\n{tl_text}"
    
    print("📤 Sending to Telegram...")
    send_telegram(final_msg)
    print("✅ Done!")
