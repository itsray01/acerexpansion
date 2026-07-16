import os
import sys
import logging
import asyncio
import subprocess
import json
import math
import threading
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
# MAP SCREENSHOT ENGINE (VIA PLAYWRIGHT)
# ==========================================
def get_map_screenshot(png_file="map_preview.png", enable_heatmap=False):
    """Uses Playwright headless Chromium to take an HD screenshot of the LIVE GitHub map."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            # CRITICAL CLOUD FIX: Added args to prevent Chromium from crashing inside Render's restricted Linux containers
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--single-process" # Prevents out-of-memory crashes on free cloud tiers
                ]
            )
            page = browser.new_page(viewport={"width": 1280, "height": 800})
            
            # Point directly to your hosted live map to bypass local file restrictions
            url = "https://itsray01.github.io/acerexpansion/acer_expansion_map.html"
            
            # Changed from 'networkidle' to 'load' because map tiles cause networkidle to time out
            page.goto(url, wait_until="load", timeout=30000)
            
            # Wait for Leaflet UI to exist before injecting JS
            page.wait_for_selector('.leaflet-control-zoom-out', timeout=15000)
            
            # Inject JS to click buttons like a real human
            js_code = """
            (enableHeatmap) => {
                // 1. Human-like Zoom Out (Click the '-' button on the map)
                const zoomOutBtn = document.querySelector('.leaflet-control-zoom-out');
                if (zoomOutBtn) {
                    zoomOutBtn.click(); // Zooms out to capture the whole island perfectly
                }

                // 2. Hide unwanted items from the Legend Box safely
                document.querySelectorAll('.legend-text').forEach(span => {
                    if (span.textContent.includes('Simulated')) {
                        if (span.parentElement) span.parentElement.style.display = 'none';
                    }
                    if (!enableHeatmap && span.textContent.includes('Heatmap')) {
                        if (span.parentElement) span.parentElement.style.display = 'none';
                    }
                });

                // 3. Human-like Heatmap Toggle (Find checkbox and click it)
                if (enableHeatmap) {
                    document.querySelectorAll('.leaflet-control-layers-selector').forEach(cb => {
                        const label = cb.closest('label');
                        if (label && label.textContent.includes('Heatmap')) {
                            if (!cb.checked) {
                                cb.click();
                            }
                        }
                    });
                }
            }
            """
            page.evaluate(js_code, enable_heatmap)
            
            # Wait 3 seconds for zoom animation and heatmap tiles to finish rendering
            page.wait_for_timeout(3000)
                
            page.screenshot(path=png_file)
            browser.close()
            
        return png_file if os.path.exists(png_file) else None
    except Exception as e:
        logging.error(f"Playwright map screenshot failed: {e}")
        return None

# ==========================================
# REPORT ANALYTICS ENGINE
# ==========================================
def calculate_haversine(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def generate_intelligence_report():
    """Reads local school and branch data to calculate untapped school zones cleanly."""
    try:
        import test_hdb_only
        branches = test_hdb_only.EXISTING_BRANCHES
        schools = test_hdb_only.load_school_db()
    except Exception as e:
        logging.error(f"Could not import test_hdb_only for report: {e}")
        return "⚠️ *Error generating intelligence:* Could not load branch or school database."

    if not schools:
        return "⚠️ *Error generating intelligence:* School database is empty."

    # Comprehensive list of Singapore towns and estates
    towns = [
        "Punggol", "Sengkang", "Tampines", "Bedok", "Pasir Ris", "Jurong West", 
        "Jurong East", "Clementi", "Bukit Batok", "Bukit Panjang", "Choa Chu Kang", 
        "Woodlands", "Yishun", "Ang Mo Kio", "Bishan", "Toa Payoh", "Hougang", 
        "Serangoon", "Bukit Timah", "Queenstown", "Bukit Merah", "Geylang", "Kallang",
        "Sembawang", "Novena", "Marine Parade", "Tengah", "Bukit Brown"
    ]
    
    unprotected_by_town = {t: 0 for t in towns}
    total_unprotected = 0
    total_schools = len(schools)

    for s in schools:
        lat, lon = s.get("lat"), s.get("lon")
        if not lat or not lon:
            continue
            
        # Check if protected by ANY existing branch (<1500m)
        is_protected = False
        for b_name, (b_lat, b_lon) in branches.items():
            if calculate_haversine(lat, lon, b_lat, b_lon) <= 1500:
                is_protected = True
                break
                
        if not is_protected:
            total_unprotected += 1
            s_name = str(s.get("name", "")).title()
            s_addr = str(s.get("address", "")).title()
            
            # Match strictly against known Singapore towns
            for t in towns:
                if t.lower() in s_name.lower() or t.lower() in s_addr.lower():
                    unprotected_by_town[t] += 1
                    break

    # Sort towns by highest unprotected count and extract exactly Top 5
    sorted_towns = sorted(unprotected_by_town.items(), key=lambda x: x[1], reverse=True)
    top_towns = [t for t in sorted_towns if t[1] > 0][:5]

    protected_count = total_schools - total_unprotected
    coverage_pct = round((protected_count / total_schools) * 100) if total_schools > 0 else 0

    report = (
        "📊 *ACER ACADEMY: EXPANSION INTELLIGENCE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *Top Untapped Towns* _(No branch <1.5km)_\n"
    )

    medals = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
    for idx, (town, count) in enumerate(top_towns):
        badge = " 🔥" if idx == 0 else ""
        report += f"{medals[idx]} *{town}* — {count} Unprotected Schools{badge}\n"

    report += (
        "\n🛡️ *Network Coverage Summary*\n"
        f"• Existing Branches: *{len(branches)}*\n"
        f"• Tracked Schools: *{total_schools}*\n"
        f"• Protected (<1.5km): *{protected_count}* ({coverage_pct}%)\n"
        f"• Unprotected Zones: *{total_unprotected}*\n\n"
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
        "• /report — Network intelligence & map preview\n"
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
    # 1. Grab the ID of the chat where the command was just typed
    chat_id = str(update.effective_chat.id)
    
    await update.message.reply_text("⏳ *Scraping HDB Place2Lease...* This will take 15-30 seconds. Please wait.", parse_mode="Markdown")
    
    def run_script():
        # 2. Copy the environment variables and temporarily overwrite the Chat ID
        custom_env = os.environ.copy()
        custom_env["TELEGRAM_CHAT_ID"] = chat_id
        
        return subprocess.run(
            [sys.executable, "test_hdb_only.py"], 
            capture_output=True, 
            text=True,
            env=custom_env # 3. Pass the custom environment to the scraper
        )

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
    
    # 1. Generate clean text intelligence (RESTORED LINE)
    intel_summary = generate_intelligence_report()
    
    try:
        loop = asyncio.get_running_loop()
        # Note: enable_heatmap=True triggers the JS to click the map layer
        img_path = await loop.run_in_executor(None, get_map_screenshot, "report_preview.png", True)
        
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=intel_summary, parse_mode="Markdown")
            return
    except Exception as e:
        logging.error(f"Failed to send photo report: {e}")
        
    # Fallback to text if screenshot fails
    await update.message.reply_text(intel_summary, parse_mode="Markdown")

async def map_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends an HD map screenshot (Standard) and provides web link."""
    await update.message.reply_text("🗺️ *Loading live interactive map snapshot...*", parse_mode="Markdown")
    
    try:
        loop = asyncio.get_running_loop()
        # Standard map view (enable_heatmap=False)
        img_path = await loop.run_in_executor(None, get_map_screenshot, "map_preview.png", False)
        
        caption_text = (
            "🗺️ *LIVE EXPANSION MAP PREVIEW*\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "Visualizing 17 Acer Academy branches & 331 school zones across Singapore.\n\n"
            "🌐 *Live Interactive Web Map:*\n"
            "[👉 Click Here to Open Interactive Map](https://itsray01.github.io/acerexpansion/acer_expansion_map.html)"
        )
        
        if img_path and os.path.exists(img_path):
            with open(img_path, 'rb') as photo:
                await update.message.reply_photo(photo=photo, caption=caption_text, parse_mode="Markdown")
        else:
            await update.message.reply_text(caption_text, parse_mode="Markdown", disable_web_page_preview=True)
            
    except Exception as e:
        logging.error(f"Error executing map command: {e}")
        await update.message.reply_text(f"❌ *Map Error:* `{str(e)}`", parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a professional guide on how to read the bot's data."""
    help_text = (
        "📖 *ACER ACADEMY: SYSTEM GUIDE*\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🎯 *The 1.5km Radius Rule*\n"
        "We use a 1.5km protective radius around existing branches. If a school falls outside this zone, it is considered an *Unprotected School*. The `/report` ranks the towns with the most unprotected schools.\n\n"
        "💵 *Understanding PSF (Per Square Foot)*\n"
        "The bot automatically cross-references HDB bids against the private commercial market:\n"
        "• *Market Rate:* The median rent for similar private units in that specific cluster.\n"
        "• *Target Bid:* Our suggested maximum bid, calculated at *65% of the private market rate*.\n"
        "• ⚠️ *(Above Market):* Flags if the current HDB bid is already higher than our target.\n\n"
        "🚦 *Cannibalization Warning*\n"
        "If a new HDB tender is less than 800m from an existing Acer Academy branch, the bot will flag it as ⚠️ *(Too Close)* to prevent stealing our own students."
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

if __name__ == '__main__':
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not TOKEN:
        print("[!] CRITICAL: TELEGRAM_BOT_TOKEN is missing from your .env file!")
        exit(1)
        
    print("[*] Initializing Acer Command Center Bot...")
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tenders", tenders))
    app.add_handler(CommandHandler("report", report))
    app.add_handler(CommandHandler("map", map_command))
    app.add_handler(CommandHandler("help", help_command))
    
    class DummyHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"<html><body><h1>Acer Bot is Awake 24/7!</h1></body></html>")

    def keep_awake():
        port = int(os.environ.get("PORT", 8080))
        server = HTTPServer(('0.0.0.0', port), DummyHandler)
        print(f"[*] Dummy web server listening on port {port}...")
        server.serve_forever()

    threading.Thread(target=keep_awake, daemon=True).start()
    
    print("[*] Bot is running and polling... Press Ctrl+C to stop.")
    app.run_polling()
