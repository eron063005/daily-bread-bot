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
    """Opens the URL using a headless browser to let JS content render completely."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_extra_http_headers({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        print(f"🌐 Loading page via Playwright: {url}")
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(4000) 
        html = page.content()
        browser.close()
        return html

def get_target_date_url():
    """Calculates the dynamic Epoch Unix timestamp matching current day in PH time zone."""
    # Kumuha ng exact date ngayon sa Philippine Time (UTC+8)
    now_ph = datetime.datetime.utcnow() + datetime.timedelta(hours=8)
    
    # Set explicitly to local midnight configuration
    midnight_ph = datetime.datetime(now_ph.year, now_ph.month, now_ph.day, 0, 0, 0)
    
    # Local converted milliseconds token data
    ts_ms = int(midnight_ph.timestamp()) * 1000
    
    # Ginamit na natin ang standard /en/devotionals directory path imbes na yung 'praying-to-grow' series track link
    direct_url = f"{BASE_URL}/en/devotionals?ts={ts_ms}"
    print(f"🎯 Generated Direct Target URL: {direct_url}")
    return direct_url

def fetch_devotion_content(url):
    """Scrapes Title, Scripture, and Devotion Text from the dynamic page."""
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
            if len(text) > 40 and "copyright" not in text.lower() and "all rights reserved" not in text.lower():
                paragraphs.append(text)
                
        content_text = "\n\n".join(paragraphs)
        return title, scripture, content_text
    except Exception as e:
        print(f"❌ Content fetch error: {str(e)}")
        return "Error", "", f"Error: {str(e)}"

def generate_soap_format(title, scripture, content):
    """Uses Gemini API to process the content into a super casual Taglish SOAP format."""
    if not content or content.startswith("Error"):
        return "Can't process the devotion text. Looks like something went wrong with the scraper."
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        prompt = f"""
You are an expert Christian writer creating an inspiring daily reflection block. 
Based on the following English devotion, create a response strictly in the requested structure.

CRITICAL TONE REQUIREMENT: 
Write the reflection items in a SUPER CASUAL, natural, and conversational Taglish/Tagalog (the exact way young adult urban Filipinos chat or message each other online). 
Do NOT use deeply formal, traditional, or old Tagalog words. 
- Instead of "sakripisyo", use "sacrifice".
- Instead of "pag-alaala/pag-obserba", use "pag-alala" or "pagre-remind".
- Instead of "gawi", use "habit" or "practice".
- Instead of "ipinahahayag", use "shine-share" or "ino-observe".
Make it feel like a text message from a close friend. Warm, chill, relatable, and extremely easy to absorb.

Here is the devotion data:
Title: {title}
Scripture Reference: {scripture}
Content: {content}

Output Format Required (Follow this exact layout and wording for headings):

📖 Brief Summary (short lang)
[Write a short, super casual summary paragraph in Taglish explaining the story and core message]

🧾 SOAP (Taglish casual, paragraph form)
S (Scripture):
[Write down the verse or reference and what it says in 1-2 very casual Taglish sentences]

O (Observation):
[Write a short paragraph analyzing the context, what God wants us to learn, and what it implies in a chatty, conversational tone]

A (Application):
[Write a highly practical personal application paragraph starting with "Sa araw-araw..." or "Gusto kong..." on how to live this out]

P (Prayer):
[Write a short conversational prayer in casual Taglish starting with "Lord..." and ending with "Amen."]

⭐ Important Points (short lang)
[Bullet point 1 using short, punchy casual Taglish]
[Bullet point 2 using short, punchy casual Taglish]
[Bullet point 3 using short, punchy casual Taglish]
[Bullet point 4 using short, punchy casual Taglish]
[Bullet point 5 using short, punchy casual Taglish]

🎯 One-Sentence Takeaway
[Provide a punchy, memorable one-sentence concluding takeaway in casual Taglish with relevant emojis]
"""
        
        print("🤖 Generating SUPER CASUAL SOAP text via Gemini AI...")
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        print(f"❌ AI Generation Error: {str(e)}")
        return "⚠️ Failed to generate SOAP format due to an AI processing error."

def send_telegram(message):
    """Sends the final message block to Telegram, chunking it if it hits limits."""
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
    print("🔍 Generating today's target URL via global timestamp calculation...")
    daily_url = get_target_date_url()
    
    print("📥 Scraping content...")
    title, scripture, content = fetch_devotion_content(daily_url)
    
    print("✨ Processing with AI for customized format...")
    ai_analysis = generate_soap_format(title, scripture, content)

    # Philippine Time (Base on UTC+8)
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
