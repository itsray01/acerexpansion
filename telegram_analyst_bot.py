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
        # Double check cache inside the lock (in case the Ghost Task JUST finished making it while we waited in line)
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
                
                # Wait for 'load' to ensure the Leaflet JS has actually executed
                page.goto(url, wait_until="load", timeout=45000)
                
                # Give base map tiles a few seconds to visually populate
                page.wait_for_timeout(5000)
                
                # Inject JS to click buttons like a real human
                js_code = """
                (enableHeatmap) => {
                    const zoomOutBtn = document.querySelector('.leaflet-control-zoom-out');
                    if (zoomOutBtn) zoomOutBtn.click();

                    document.querySelectorAll('.legend-text').forEach(span => {
                        if (span.textContent.includes('Simulated')) {
                            if (span.parentElement) span.parentElement.style.display = 'none';
                        }
                        if (!enableHeatmap && span.textContent.includes('Heatmap')) {
                            if (span.parentElement) span.parentElement.style.display = 'none';
                        }
                    });

                    if (enableHeatmap) {
                        document.querySelectorAll('.leaflet-control-layers-selector').forEach(cb => {
                            const label = cb.closest('label');
                            if (label && label.textContent.includes('Heatmap') && !cb.checked) {
                                cb.click();
                            }
                        });
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

    report = ("📊 *ACER ACADEMY: EXPANSION INTELLIGENCE*\n━━━━━━━━━━━━━━━━━━━━━━━━\n\n🎯 *Top Untapped Towns* _(No branch <1.5km)_\n")
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
        f"_Prioritize upcoming HDB commercial tenders
