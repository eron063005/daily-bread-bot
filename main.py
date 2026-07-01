import os
import urllib.parse
import datetime
import requests
from bs4 import BeautifulSoup
from google import genai
from playwright.sync_api import sync_playwright

# ================= CONFIG =================
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BASE_URL = "https://www.odbm.org"
# ===========================================

def fetch_html_with_playwright(url):
    """Binubuksan ang URL gamit ang headless browser para mag-render ang JS content."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        print(f"🌐 Loading page via Playwright: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        html = page.content()
        browser.close()
        return html

def fetch_todays_devotion_url():
    """Kunin ang link ng devotion mula sa rendered HTML"""
    url = f"{BASE_URL}/en/devotionals"
    try:
        html = fetch_html_with_playwright(url)
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: Hanapin ang text na may "Today's Devotion"
        today_label = soup.find(lambda tag: tag.name in ["div", "span", "p", "h3"] and tag.text and "Today's Devotion" in tag.text)
        if today_label:
            link_tag = today_label.find_parent("a", href=True)
            if link_tag and link_tag.get("href"):
                return urllib.parse.urljoin(BASE_URL, link_tag["href"])

        # Strategy 2: Fallback sa unang nakitang devotional category link
        first_link = soup.find("a", href=lambda h: h and "/devotional-category/" in h)
        if first_link:
            return urllib.parse.urljoin(BASE_URL, first_link["href"])

        return None
    except Exception as e:
        print(f"❌ Error fetching URL: {str(e)}")
        return None

def fetch_devotion_content(url):
    """I-scrape ang Title, Scripture, at Devotion Text mula sa dynamic page"""
    try:
        html = fetch_html_with_playwright(url)
        soup = BeautifulSoup(html, "html.parser")

        # Title
        title_tag = soup.find("h1") or soup.find("h2")
        title = title_tag.get_text(strip=True) if title_tag else "Daily Devotion"

        # Scripture Reference
        scripture = ""
        scripture_btn = soup.find("button", attrs={"aria-label": lambda a: a and ":" in a}) or soup.find("button", string=lambda t: t and ":" in t)
        if scripture_btn:
            scripture = scripture_btn.get_text(strip=True)
        
        # Main Devotion Content
        paragraphs = []
        all_p = soup.find_all("p")
        for p in all_p:
            text = p.get_text(strip=True)
            # Salain ang mga basurang text tulas ng copyright statements o maiikling menu items
            if len(text) > 40 and "copyright" not in text.lower() and "all rights reserved" not in text.lower():
                paragraphs.append(text)
                
        content_text = "\n\n".join(paragraphs)
        return title, scripture, content_text
    except Exception as e:
        print(f"❌ Content fetch error: {str(e)}")
        return "Error", "", f"Error: {str(e)}"

def generate_soap_format(title, scripture, content):
    """Ginagamit ang Gemini API para gawin ang custom SOAP format"""
    if not content or content.startswith("Error"):
        return "Hindi makuha ang nilalaman ng devotion upang magawan ng SOAP format."
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
You are an expert Christian writer creating an inspiring daily reflection block. 
Based on the following English devotion, create a response strictly in the requested structure.
The core reflection items should be written in a conversational, relatable Taglish/Tagalog (casual paragraph form for SOAP).

Here is the devotion data:
Title: {title}
Scripture Reference: {scripture}
Content: {content}

Output Format Required (Follow this exact layout and wording for headings):

📖 Brief Summary (short lang)
[Write a short summary paragraph in Tagalog explaining the story and core message]

🧾 SOAP (Taglish casual, paragraph form)
S (Scripture):
[Write down the verse or reference and what it says in 1-2 Tagalog sentences]

O (Observation):
[Write a short paragraph analyzing the context, what God wants us to learn from this, and what it implies]

A (Application):
[Write a highly practical personal application paragraph starting with "Sa araw-araw..." or "Gusto kong..." on how to live this out]

P (Prayer):
[Write a short conversational prayer in Tagalog starting with "Lord..." and ending with "Amen."]

⭐ Important Points (short lang)
[Bullet point 1]
[Bullet point 2]
[Bullet point 3]
[Bullet point 4]
[Bullet point 5]

🎯 One-Sentence Takeaway
[Provide a punchy, memorable one-sentence concluding takeaway in Tagalog with relevant emojis]
"""
        
        print("🤖 Generating SOAP text via Gemini AI...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"❌ AI Generation Error: {str(e)}")
        return "⚠️ Error sa pag-proseso ng AI para sa SOAP structure."

def send_telegram(message):
    """I-send ang pinal na mensahe sa Telegram (hinahati kung lumampas sa limit)"""
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
    # Maaari ring palitan ng hardcoded link para sa testing: daily_url = "https://www.odbm.org/en/devotionals/devotional-category/praying-to-grow?ts=1782691200000"
    daily_url = fetch_todays_devotion_url()
    
    if not daily_url:
        print("❌ Failed to get URL.")
        title, scripture, content = "Error", "", "Hindi makuha ang devotion ngayon. Subukan ulit bukas."
        ai_analysis = content
    else:
        print("📥 Scraping content...")
        title, scripture, content = fetch_devotion_content(daily_url)
        print("✨ Processing with AI for customized format...")
        ai_analysis = generate_soap_format(title, scripture, content)

    # Philippine Time (UTC+8)
    today_ph = (datetime.datetime.utcnow() + datetime.timedelta(hours=8)).strftime("%B %d, %Y")
    
    final_msg = (
        f"🍞 Daily Bread (Tagalog) {today_ph}\n\n"
        f"📌 Title: {title}\n"
        f"📖 Verse: {scripture}\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{ai_analysis}"
    )
    
    print("📤 Sending final layout to Telegram...")
    send_telegram(final_msg)
    print("✅ Finished script!")
