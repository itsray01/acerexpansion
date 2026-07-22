import os
# CRITICAL CLOUD FIX: Force Playwright to install in the local directory so Render doesn't delete it
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0" 

import sys
import logging
import asyncio
import subprocess
import json
import math
import threading
import time 
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import ReplyKeyboardMarkup, KeyboardButton, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from dotenv import load_dotenv

# 1. Force load credentials
load_dotenv()

# 2. Setup Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)

# ==========================================
# GLOBAL CLOUD STATE & MEMORY LOCKS
# ==========================================
IS_INSTALLING = True
# A Threading Lock ensures Render's 512MB RAM is never overwhelmed by multiple Chrome instances
BROWSER_LOCK = threading.Lock() 

# ==========================================
# RENDER.COM 24/7 CLOUD SURVIVAL ENGINE
# ==========================================
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Acer Bot is Awake 24/7!</h1></body></html>")
        
    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

def keep_awake():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    print(f"[*] Dummy web server listening on port {port}...")
    server.serve_forever()

# ==========================================
# MAP SCREENSHOT ENGINE (VIA PLAYWRIGHT)
# ==========================================
def get_map_screenshot(png_file="map_preview.png", enable_heatmap=False, force_refresh=False):
    """Uses Playwright headless Chromium to take an HD screenshot of the LIVE GitHub map."""
    global IS_INSTALLING
    
    # 1. Graceful Warm-up Check
    if IS_INSTALLING:
        return None, "⏳ *Warming Up:* The cloud server is currently downloading the map engine. Please try again in 60 seconds!"
        
    # 2. SMART CACHE SYSTEM: Instantly return if less than 12 hours old
    if not force_refresh and os.path.exists(png_file):
        file_age_seconds = time.time() - os.path.getmtime(png_file)
        if file_age_seconds < 43200: # 12 hours
            logging.info(f"[*] Serving cached {png_file} (Age: {int(file_age_seconds/60)} mins)")
            return png_file, None

    # 3. MEMORY LOCK: Only one thread can open Chrome at a time!
    with BROWSER_LOCK:
        # Double check cache inside the lock
        if not force_refresh and os.path.exists(png_file):
            file_age_seconds = time.time() - os.path.getmtime(png_file)
            if file_age_seconds < 43200:
                return png_file, None
                
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",               
                        "--no-zygote",
                        "--disable-software-rasterizer"
                    ]
                )
                context = browser.new_context(viewport={"width": 1280, "height": 800})
                page = context.new_page()
                
                url = "https://itsray01.github.io/acerexpansion/acer_expansion_map.html"
                
                # Wait for domcontentloaded to ensure the Leaflet JS has actually executed without timing out
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                
                # BUG FIX: Wait for the main leaflet container, NOT the zoom buttons (which we deleted!)
                try:
                    page.wait_for_selector('.leaflet-container', timeout=15000)
                except Exception as e:
                    logging.warning(f"Timeout waiting for map container: {e}")
                
                # Give base map tiles a few seconds to visually populate
                page.wait_for_timeout(5000)
                
                # Inject JS to click buttons like a real human and scale UI elements for Screenshots
                js_code = """
                (enableHeatmap) => {
                    // UI OVERRIDE: Scale down the legend exclusively for bot screenshots
                    const legend = document.getElementById('map-legend');
                    if (legend) {
                        legend.style.transform = 'scale(0.75)';
                        legend.style.transformOrigin = 'top left';
                    }

                    // Manage Layers via Leaflet Control UI
                    document.querySelectorAll('input.leaflet-control-layers-selector').forEach(cb => {
                        const label = cb.closest('label');
                        if (!label) return;
                        const txt = label.textContent;

                        // ALWAYS hide the simulation pin in bot screenshots
                        if (txt.includes('Simulate') && cb.checked) {
                            cb.click();
                        }

                        // UI OVERRIDE: ALWAYS hide Regional Data Boxes in screenshots so they look clean
                        if (txt.includes('Regional Data Boxes') && cb.checked) {
                            cb.click();
                        }
                        
                        // ENSURE Competitors and BTOs are ON in screenshots
                        if (txt.includes('Competitor Network') && !cb.checked) {
                            cb.click();
                        }
                        if (txt.includes('Upcoming BTO Estates') && !cb.checked) {
                            cb.click();
                        }
                        
                        // Toggle Heatmap ON if requested (for /report)
                        if (enableHeatmap && txt.includes('Heatmap') && !cb.checked) {
                            cb.click();
                        }
                    });

                    // UI OVERRIDE: Force Ender Dragon bar to show for /report screenshots
                    if (enableHeatmap) {
                        const healthBar = document.getElementById('heatmap-health-bar');
                        if (healthBar) healthBar.style.display = 'block';
                    }
                }
                """
                page.evaluate(js_code, enable_heatmap)
                
                # Wait 4 seconds for zoom animation and heatmap tiles to finish rendering
                page.wait_for_timeout(4000)
                    
                page.screenshot(path=png_file)
                browser.close()
                
            return png_file, None
        except Exception as e:
            logging.error(f"Playwright map screenshot failed: {e}")
            return None, str(e)

# ==========================================
# REPORT ANALYTICS ENGINE
# ==========================================
def calculate_haversine(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def generate_intelligence_report():
    try:
        import test_hdb_only
        branches = test_hdb_only.EXISTING_BRANCHES
        schools = test_hdb_only.load_school_db()
    except Exception as e:
        return "⚠️ *Error generating intelligence:* Could not load branch or school database."

    if not schools:
        return "⚠️ *Error generating intelligence:* School database is empty."

    towns = ["Punggol", "Sengkang", "Tampines", "Bedok", "Pasir Ris", "Jurong West", 
             "Jurong East", "Clementi", "Bukit Batok", "Bukit Panjang", "Choa Chu Kang", 
             "Woodlands", "Yishun", "Ang Mo Kio", "Bishan", "Toa Payoh", "Hougang", 
             "Serangoon", "Bukit Timah", "Queenstown", "Bukit Merah", "Geylang", "Kallang",
             "Sembawang", "Novena", "Marine Parade", "Tengah", "Bukit Brown"]
    
    unprotected_by_town = {t: 0 for t in towns}
    total_unprotected = 0
    total_schools = len(schools)

    for s in schools:
        lat, lon = s.get("lat"), s.get("lon")
        if not lat or not lon: continue
            
        is_protected = False
        for b_name, (b_lat, b_lon) in branches.items():
            if calculate_haversine(lat, lon, b_lat, b_lon) <= 1500:
                is_protected = True
                break
                
        if not is_protected:
            total_unprotected += 1
            s_name = str(s.get("name", "")).title()
            s_addr = str(s.get("address", "")).title()
            for t in towns:
                if t.lower() in s_name.lower() or t.lower() in s_addr.lower():
                    unprotected_by_town[t] += 1
                    break

    sorted_towns = sorted(unprotected_by_town.items(), key=lambda x: x[1], reverse=True)
    top_towns = [t for t in sorted_towns if t[1] > 0][:5]

    protected_count = total_schools - total_unprotected
    coverage_pct = round((protected_count / total_schools) * 100) if total_schools > 0 else 0

    # Phrasing polished to Unserved Schools / Zones
    report = ("📊 *ACER ACADEMY: EXPANSION INTELLIGENCE*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎯 *Top Untapped Towns* _(No branch <1.5km)_\n")
    medals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for idx, (town, count) in enumerate(top_towns):
        badge = " 🔥" if idx == 0 else ""
        report += f"{medals[idx]} *{town}* — {count} Unserved Schools{badge}\n"

    report += (
        "\n🛡️ *Network Coverage Summary*\n"
        f"• Existing Branches: *{len(branches)}*\n"
        f"• Tracked Schools: *{total_schools}*\n"
        f"• Protected (<1.5km): *{protected_count}* ({coverage_pct}%)\n"
        f"• Unserved Zones: *{total_unprotected}*\n\n"
        "💡 *Strategic Takeaway:*\n"
        f"_Prioritize upcoming HDB commercial tenders in *{top_towns[0][0]}* and *{top_towns[1][0]}* to capture the highest density of unserved students._"
    )
    return report

# ==========================================
# BOT COMMAND HANDLERS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a professional welcome card and enables a custom mobile keyboard."""
    welcome_text = (
        "🏢 *ACER ACADEMY: COMMAND CENTER* 🏢\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Welcome to the automated HDB tender & expansion intelligence system.\n\n"
        "📱 *Available Commands:*\n"
        "• /tenders — Scrape latest HDB Place2Lease listings\n"
        "• /report — Network intelligence & heatmap preview\n"
        "• /map — Render map screenshot & access web link\n"
        "• /help — How to read the data & metrics\n\n"
        "_Select an option from the menu below to begin:_"
    )
    
    keyboard = [
        [KeyboardButton("/tenders"), KeyboardButton("/report")],
        [KeyboardButton("/map"), KeyboardButton("/help")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, is_persistent=True)
    
    await update.message.reply_text(welcome_text, parse_mode="Markdown", reply_markup=reply_markup)

async def tenders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Runs the HDB scraper via a safe background subprocess."""
    chat_id = str(update.effective_chat.id)
    await update.message.reply_text("⏳ *Scraping HDB Place2Lease...* This will take 15-30 seconds. Please wait.", parse_mode="Markdown")
    
    def run_script():
        custom_env = os.environ.copy()
        custom_env["TELEGRAM_CHAT_ID"] = chat_id
        return subprocess.run([sys.executable, "test_hdb_only.py"], capture_output=True, text=True, env=custom_env)

    try:
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, run_script)
        
        if result.returncode == 0:
            await update.message.reply_text("✅ *HDB data pipeline finished successfully!* Check above for new listing alerts.", parse_mode="Markdown")
        else:
            error_msg = result.stderr[:500] if result.stderr else "Unknown error occurred."
            await update.message.reply_text(f"⚠️ *Scraper completed with warnings/errors:*\n```text\n{error_msg}\n```", parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Failed to execute scraper subprocess: {e}")
        await update.message.reply_text(f"❌ *Critical Error:* Could not run script.\n`{str(e)}`", parse_mode="Markdown")

async def report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends the analytical mobile summary embedded as a photo caption with HEATMAP screenshot!"""
    await update.message.reply_text("📊 *Calculating coverage & snapping heatmap...*", parse_mode="Markdown")
    
    intel_summary = generate_intelligence_report()
    err = None
    
    try:
        loop = asyncio.get_running_loop()
        # force_refresh=True to make sure it captures the newly forced ON BTOs and Competitors
        img_path, err = await loop.run_in_executor(None, get_map_screenshot, "report_preview.png", True, True)
        
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=intel_summary, parse_mode="Markdown")
            return
    except Exception as e:
        err = str(e)
        logging.error(f"Failed to send photo report: {e}")
        
    if err:
        intel_summary += f"\n\n⚠️ *Debug - Screenshot Error:*\n`{err[:250]}`"
        
    await update.message.reply_text(intel_summary, parse_mode="Markdown")

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends an HD map screenshot (Standard) and provides web link."""
    await update.message.reply_text("🗺️ *Loading live interactive map snapshot...*", parse_mode="Markdown")
    
    err = None
    caption_text = (
        "🗺️ *LIVE EXPANSION MAP PREVIEW*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Visualizing Acer Academy branches & 331 school zones across Singapore.\n\n"
        "🌐 *Live Interactive Web Map:*\n"
        "[👉 Click Here to Open Interactive Map](https://itsray01.github.io/acerexpansion/acer_expansion_map.html)"
    )
    
    try:
        loop = asyncio.get_running_loop()
        # force_refresh=True to make sure it captures the newly forced ON BTOs and Competitors
        img_path, err = await loop.run_in_executor(None, get_map_screenshot, "map_preview.png", False, True)
        
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=caption_text, parse_mode="Markdown")
            return
    except Exception as e:
        err = str(e)
        logging.error(f"Error executing map command: {e}")
        
    if err:
        caption_text += f"\n\n⚠️ *Debug - Screenshot Error:*\n`{err[:250]}`"
        
    await update.message.reply_text(caption_text, parse_mode="Markdown", disable_web_page_preview=True)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a professional guide on how to read the bot's data."""
    help_text = (
        "📖 *ACER ACADEMY: SYSTEM GUIDE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *The 1.5km Radius Rule*\n"
        "We use a 1.5km protective radius around existing branches. If a school falls outside this zone, it is considered an *Unserved School*. The `/report` ranks the towns with the most unserved schools.\n\n"
        "💵 *Understanding PSF (Per Square Foot)*\n"
        "The bot automatically cross-references HDB bids against the private commercial market:\n"
        "• *Market Rate:* The median rent for similar private units in that specific cluster.\n"
        "• *Target Bid:* Our suggested maximum bid, calculated at *65% of the private market rate*.\n"
        "• ⚠️ *(Above Market):* Flags if the current HDB bid is already higher than our target.\n\n"
        "🚦 *Cannibalization Warning*\n"
        "If a new HDB tender is less than 800m from an existing Acer Academy branch, the bot will flag it as ⚠️ *(Too Close)* to prevent stealing our own students."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ==========================================
# BACKGROUND GHOST TASK
# ==========================================
async def auto_cache_maps_background():
    """Runs forever in the background, updating the map caches every 12 hours."""
    global IS_INSTALLING
    logging.info("[*] GHOST TASK: Verifying Playwright Browser Binaries in background...")
    loop = asyncio.get_running_loop()
    
    try:
        # 1. Background Download
        await loop.run_in_executor(
            None, 
            subprocess.run, 
            [sys.executable, "-m", "playwright", "install", "chromium"]
        )
    except Exception as e:
        logging.error(f"[!] Browser install failed: {e}")

    # 2. Release Lock
    IS_INSTALLING = False
    logging.info("[*] GHOST TASK: Browser ready. Generating fresh map caches in 5 seconds...")
    await asyncio.sleep(5)

    # 3. Endless Caching Loop
    while True:
        logging.info("[*] GHOST TASK: Generating fresh map caches in the background...")
        try:
            await loop.run_in_executor(None, get_map_screenshot, "map_preview.png", False, True)
            await loop.run_in_executor(None, get_map_screenshot, "report_preview.png", True, True)
            logging.info("[*] GHOST TASK: Map caches successfully updated! Sleeping for 12 hours.")
        except Exception as e:
            logging.error(f"[!] GHOST TASK FAILED: {e}")
            
        await asyncio.sleep(43200)

async def post_init(application: ApplicationBuilder):
    """Fires automatically the exact second the bot connects to Telegram."""
    asyncio.create_task(auto_cache_maps_background())

if __name__ == '__main__':
    # 1. Start the Render web server instantly
    threading.Thread(target=keep_awake, daemon=True).start()

    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        print("[!] CRITICAL: TELEGRAM_BOT_TOKEN is missing from your .env file!")
        exit(1)
        
    print("[*] Initializing Acer Command Center Bot...")
    # 2. Add the post_init hook to trigger our background caching task
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tenders", tenders))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(CommandHandler("help", help_command))
    
    print("[*] Bot is running and polling... Press Ctrl+C to stop.")
    app.run_polling()
