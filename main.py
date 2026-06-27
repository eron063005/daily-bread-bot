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
    print("❌ ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not found in Secrets!")
    exit(1)

def fetch_todays_devotion_url():
    """Kunin ang link ng TODAY'S devotion"""
    url = f"{BASE_URL}/en/devotionals"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Hanapin ang div na may text na "Today's Devotion", tapos kunin ang parent <a> tag
        today_label = soup.find("div", string=lambda text: text and "Today's Devotion" in text)
        if today_label:
            link = today_label.find_parent("a", href=True)
            if link and link.get("href"):
                daily_url = link["href"]
                if daily_url.startswith("/"):
                    daily_url = BASE_URL + daily_url
                print(f"✅ Found today's URL: {daily_url}")
                return daily_url
                
        # Fallback: Unang link na may /devotional-category/
        fallback = soup.find("a", href=lambda h: h and "/devotional-category/" in h)
        if fallback:
            daily_url = fallback["href"]
            if daily_url.startswith("/"):
                daily_url = BASE_URL + daily_url
            print(f"⚠️ Using fallback URL: {daily_url}")
            return daily_url
            
        return None
    except Exception as e:
        print(f"❌ URL fetch error: {str(e)}")
        return None

def fetch_devotion_content(url):
    """I-scrape ang Title, Scripture Ref, at Main Devotion Text"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # 1. Title (nasa h1 na may class na text-4xl at text-white)
        title_tag = soup.find("h1", class_=lambda c: c and "text-4xl" in c)
        title = title_tag.get_text(strip=True) if title_tag else "Daily Devotion"
        
        # 2. Scripture Reference (nasa button na may aria-label)
        scripture_btn = soup.find("button", attrs={"aria-label": lambda a: a and ":" in a})
        scripture = scripture_btn.get_text(strip=True) if scripture_btn else "Scripture not available"
        
        # 3. Main Devotion Content (nasa loob ng div pagkatapos ng <h2>Today's Devotion</h2>)
        devotion_header = soup.find("h2", string=lambda text: text and "Today's Devotion" in text)
        content_text = ""
        
        if devotion_header:
            # Kunin ang next sibling div na naglalaman ng mga <p> tags
            content_wrapper = devotion_header.find_next_sibling("div")
            if content_wrapper:
                paragraphs = content_wrapper.find_all("p")
                content_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                
        # Fallback kung hindi nahanap ang specific wrapper
        if not content_text:
            rich_text = soup.find("div", class_=lambda c: c and "rich-text" in c)
            if rich_text:
                paragraphs = rich_text.find_all("p")
                content_text = "\n\n".join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                
        if not content_text:
            content_text = "Hindi makuha ang content ngayong araw. Subukan ulit bukas."
            
        return title, scripture, content_text
    except Exception as e:
        print(f"❌ Content fetch error: {str(e)}")
        return "Error", "", f"Error: {str(e)}"

def translate_text(text):
    """I-translate ang text sa Tagalog gamit ang Google Translate (chunked para sa limit)"""
    if not text: return ""
    try:
        chunks = [text[i:i+4500] for i in range(0, len(text), 4500)]
        translator = GoogleTranslator(source='en', target='tl')
        translated_chunks = [translator.translate(chunk) for chunk in chunks]
        return "\n\n".join(translated_chunks)
    except Exception as e:
        return f"Translation error: {str(e)}"

def send_telegram(message):
    """I-send sa Telegram (plain text para iwas markdown breaking)"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    # Hatiin kung mahaba (Telegram limit: 4096 chars)
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    
    for chunk in chunks:
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True
        }
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code != 200:
            print(f"❌ Telegram API Error: {response.text}")
        else:
            print("✅ Successfully sent to Telegram!")

if __name__ == "__main__":
    print("🔍 Finding today's devotion URL...")
    daily_url = fetch_todays_devotion_url()
    
    if not daily_url:
        print("❌ Could not find today's devotion URL.")
        exit(1)
        
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
