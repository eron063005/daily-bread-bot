import os
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import datetime

# ================= CONFIG =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BASE_URL = "https://www.odbm.org"
# ===========================================

if not BOT_TOKEN or not CHAT_ID:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found!")
    exit(1)

def fetch_todays_devotion_url():
    """Kunin ang link ng TODAY'S devotion mula sa main page"""
    url = f"{BASE_URL}/en/devotionals"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # ✅ CORRECT SELECTOR: Hanapin ang h3 na may "Today's Devotion", tapos ang next <a> tag
        today_heading = soup.find("h3", string=lambda text: text and "Today's Devotion" in text)
        
        if today_heading:
            today_link = today_heading.find_next("a", href=True)
            if today_link and today_link.get("href"):
                daily_url = today_link["href"]
                if daily_url.startswith("/"):
                    daily_url = BASE_URL + daily_url
                print(f"✅ Found today's devotion URL: {daily_url}")
                return daily_url
        
        # Fallback: kunin ang first devotion card
        first_card = soup.find("a", href=lambda href: href and "/devotional-category/" in href)
        if first_card:
            daily_url = first_card["href"]
            if daily_url.startswith("/"):
                daily_url = BASE_URL + daily_url
            print(f"⚠️ Using fallback URL: {daily_url}")
            return daily_url
            
        return None
    except Exception as e:
        print(f"❌ Error fetching URL: {str(e)}")
        return None

def fetch_devotion_content(url):
    """I-scrape ang actual content ng devotion page"""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # ✅ Title: usually h1
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Daily Devotion"
        
        # ✅ Scripture: hanapin ang section na may "Today's Scripture"
        scripture = ""
        scripture_label = soup.find(string=lambda text: text and "Today's Scripture" in text)
        if scripture_label:
            scripture_container = scripture_label.find_parent() or scripture_label.find_next()
            if scripture_container:
                scripture = scripture_container.get_text(strip=True)
        
        # ✅ Content: try multiple common selectors
        content = ""
        content_selectors = [
            {"class_": "devotion-content"},
            {"class_": "article-body"},
            {"name": "article"},
            {"attrs": {"itemprop": "articleBody"}},
            {"class_": "prose"},  # Tailwind common class
        ]
        
        for selector in content_selectors:
            content_div = soup.find(**selector)
            if content_div:
                # Tanggalin ang mga hindi kailangan
                for tag in content_div(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                content = content_div.get_text(separator="\n", strip=True)
                if len(content) > 100:  # Valid content should be long enough
                    break
        
        # Fallback: kunin ang mga meaningful paragraphs
        if not content or len(content) < 100:
            paragraphs = soup.find_all("p")
            meaningful_p = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
            content = "\n\n".join(meaningful_p[:10])  # Limit to first 10 meaningful paragraphs
        
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
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    
    for chunk in chunks:
        payload = {"chat_id": CHAT_ID, "text": chunk, "parse_mode": "Markdown"}
        response = requests.post(url, json=payload, timeout=30)
        print(f"📡 Telegram Status: {response.status_code}")
        if response.status_code != 200:
            print(f"⚠️ Error: {response.text}")

if __name__ == "__main__":
    print("🔍 Finding today's devotion URL...")
    daily_url = fetch_todays_devotion_url()
    
    if not daily_url:
        print("❌ Could not find today's devotion URL.")
        eng_text = "Sorry, hindi makuha ang today's devotion. Subukan ulit bukas."
    else:
        print("📥 Fetching content...")
        eng_text = fetch_devotion_content(daily_url)
    
    print("🌐 Translating to Tagalog...")
    tl_text = translate_text(eng_text)
    
    today = datetime.date.today().strftime("%B %d, %Y")
    final_msg = f"🍞 *Daily Bread (Tagalog)*\n📅 {today}\n\n{tl_text}"
    
    print("📤 Sending to Telegram...")
    send_telegram(final_msg)
    print("✅ Done!")
