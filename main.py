import os
import requests
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator
import datetime
import re
import pytz

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
        
        # === DEBUG: Print relevant sections ===
        print("🔍 Searching for 'Today's Devotion' section...")
        
        # Strategy 1: Find h3 with "Today's Devotion", then get the NEXT <a> with href
        today_heading = soup.find("h3", string=lambda text: text and "Today's Devotion" in text)
        if today_heading:
            print("✅ Found 'Today's Devotion' heading")
            # Get the next <a> tag that has an href (the actual link)
            today_link = today_heading.find_next("a", href=True)
            if today_link and today_link.get("href"):
                daily_url = today_link["href"]
                if daily_url.startswith("/"):
                    daily_url = BASE_URL + daily_url
                print(f"✅ Found today's devotion URL: {daily_url}")
                return daily_url
        
        # Strategy 2: Find any <a> that contains "Read Today's Devotion" text
        read_today_link = soup.find("a", string=lambda text: text and "Read Today's Devotion" in text)
        if read_today_link and read_today_link.get("href"):
            daily_url = read_today_link["href"]
            if daily_url.startswith("/"):
                daily_url = BASE_URL + daily_url
            print(f"✅ Found via 'Read Today's Devotion' text: {daily_url}")
            return daily_url
        
        # Strategy 3: Find the first devotion card after "Today's Devotion" heading
        # Look for pattern: <h3>Today's Devotion</h3> followed by <a> with image
        today_section = soup.find(string=lambda text: text and "Today's Devotion" in text)
        if today_section:
            parent = today_section.find_parent()
            if parent:
                # Look for the next <a> with an image (the devotion card)
                card_link = parent.find_next("a", href=True)
                if card_link and card_link.get("href") and "/devotional-category/" in card_link["href"]:
                    daily_url = card_link["href"]
                    if daily_url.startswith("/"):
                        daily_url = BASE_URL + daily_url
                    print(f"✅ Found via card pattern: {daily_url}")
                    return daily_url
        
        # Strategy 4: Fallback - find first link with /devotional-category/ pattern
        fallback_link = soup.find("a", href=lambda href: href and "/devotional-category/" in href)
        if fallback_link:
            daily_url = fallback_link["href"]
            if daily_url.startswith("/"):
                daily_url = BASE_URL + daily_url
            print(f"⚠️ Using fallback (first devotional-category link): {daily_url}")
            return daily_url
        
        # If nothing found, print available links for debugging
        print("❌ Could not find today's devotion. Available links with 'devotional':")
        for link in soup.find_all("a", href=lambda href: href and "devotional" in href.lower())[:5]:
            print(f"   - {link.get('href')} | Text: '{link.get_text(strip=True)[:50]}'")
        
        return None
        
    except Exception as e:
        print(f"❌ Error fetching URL: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def fetch_devotion_content(url):
    """I-scrape ang actual content ng devotion page"""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        print(f"📥 Fetching: {url}")
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        
        # Title: usually h1
        title_tag = soup.find("h1")
        title = title_tag.get_text(strip=True) if title_tag else "Daily Devotion"
        print(f"📄 Title: {title}")
        
        # Scripture: look for "Today's Scripture" label
        scripture = ""
        scripture_label = soup.find(string=lambda text: text and "Today's Scripture" in text)
        if scripture_label:
            scripture_container = scripture_label.find_parent() or scripture_label.find_next()
            if scripture_container:
                scripture = scripture_container.get_text(strip=True)
        
        # Content: try multiple selectors
        content = ""
        content_selectors = [
            {"class_": "devotion-content"},
            {"class_": "article-body"},
            {"name": "article"},
            {"attrs": {"itemprop": "articleBody"}},
            {"class_": "prose"},
            {"class_": "content"},
        ]
        
        for selector in content_selectors:
            content_div = soup.find(**selector)
            if content_div:
                for tag in content_div(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()
                content = content_div.get_text(separator="\n", strip=True)
                if len(content) > 100:
                    break
        
        # Fallback: get meaningful paragraphs
        if not content or len(content) < 100:
            paragraphs = soup.find_all("p")
            meaningful_p = [p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30]
            content = "\n\n".join(meaningful_p[:10])
        
        if not content or len(content) < 50:
            print(f"⚠️ Warning: Content seems short ({len(content)} chars)")
            # Print first 500 chars of page for debugging
            print(f"🔍 Page preview: {soup.get_text()[:500]}...")
        
        full_text = f"{title}\n\n📖 Scripture:\n{scripture}\n\n📝 Devotion:\n{content}"
        return full_text
    except Exception as e:
        print(f"❌ Error fetching content: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"❌ Error: {str(e)}"

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
    
    ph_tz = pytz.timezone("Asia/Manila")
    today = datetime.datetime.now(ph_tz).strftime("%B %d, %Y")
    final_msg = f"🍞 *Daily Bread (Tagalog)*\n📅 {today}\n\n{tl_text}"
    
    print("📤 Sending to Telegram...")
    send_telegram(final_msg)
    print("✅ Done!")
