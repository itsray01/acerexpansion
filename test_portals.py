import os
import re
import json
import math
import time
import requests
from bs4 import BeautifulSoup

# ==========================================
# 1. CONFIGURATION & TEST CREDENTIALS
# ==========================================
# Pre-production test environment credentials
TELEGRAM_BOT_TOKEN = "8891294738:AAGOuTbxEhZe0Y0wBX0cOFFonFp5m_1bvdA"
TELEGRAM_CHAT_ID = "-1004306469919"
ZENROWS_API_KEY = "0a72b44b388084523647e4dce2f6787701a1fbd6" # Hardcoded for test environment

STATE_FILE = "seen_listings.json"
MAX_SQFT_LIMIT = 1200.0
MAX_PSF_THRESHOLD = 15.0

# Target Expansion Clusters for Acer Academy
TARGET_CLUSTERS = [
    # West Cluster
    "JURONG", "CLEMENTI", "BUKIT BATOK", "CHOA CHU KANG", "BUKIT PANJANG", "BOON LAY",
    # Central Cluster
    "TOA PAYOH", "BISHAN", "KALLANG", "WHAMPOA", "QUEENSTOWN", "BUKIT MERAH", "CENTRAL AREA", "NOVENA",
    # East & NE Cluster
    "SERANGOON", "HOUGANG", "SENGKANG", "PUNGGOL", "TAMPINES", "BEDOK", "PASIR RIS", "GEYLANG", "KOVAN"
]

# Existing 17 Branches for Cannibalization Math (Lat, Lon)
EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4331, 103.8405),
    "Admiralty Place (North)": (1.4402, 103.8008),
    "The Woodgrove (North)": (1.4310, 103.7845),
    "Vista Point (North)": (1.4300, 103.7920),
    "Canberra Plaza (North)": (1.4430, 103.8300),
    "Tampines West (East)": (1.3503, 103.9358),
    "Buangkok Square (East)": (1.3838, 103.8820),
    "Aljunied Maths/Science (East)": (1.3193, 103.8831),
    "Aljunied Languages (East)": (1.3195, 103.8833),
    "Elias Mall (East)": (1.3780, 103.9430),
    "Dawson (Central)": (1.2950, 103.8110),
    "Depot Heights (Central)": (1.2806, 103.8080),
    "Tiong Bahru (Central)": (1.2865, 103.8260),
    "Cantonment (Central)": (1.2755, 103.8400),
    "Commonwealth (Central)": (1.3030, 103.7990),
    "Senja Heights (West)": (1.3850, 103.7610),
    "Greenridge (West)": (1.3860, 103.7710),
    "Hong Kah (West)": (1.3520, 103.7250)
}

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth's radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    return R * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))

def check_cannibalization(target_lat, target_lon):
    nearest_branch, min_dist = None, float('inf')
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        dist = calculate_haversine_distance(target_lat, target_lon, lat, lon)
        if dist < min_dist:
            min_dist, nearest_branch = dist, name
    return nearest_branch, min_dist

def get_onemap_data(address):
    try:
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={address}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
        res = requests.get(url, timeout=10).json()
        if res.get("found", 0) > 0:
            result = res["results"][0]
            return float(result["LATITUDE"]), float(result["LONGITUDE"])
    except Exception:
        pass
    return None, None

def load_seen_listings():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen_listings(seen_set):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen_set), f, indent=2)

def send_telegram_alert(markdown_message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": markdown_message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    res = requests.post(url, json=payload)
    if res.status_code != 200:
        print(f"[!] Telegram send failed: {res.text}")
    else:
        print("[+] Telegram alert sent successfully.")

def fetch_html_safe(url):
    """Routes requests through ZenRows Universal Scraper API to bypass anti-bot shields."""
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    params = {
        "url": url,
        "apikey": ZENROWS_API_KEY,
        "js_render": "true",       # Tells ZenRows to render JavaScript elements
        "premium_proxy": "true"    # Uses high-trust residential IPs to bypass firewalls
    }
    try:
        print(f"[*] Requesting page via ZenRows API...")
        res = requests.get(zenrows_endpoint, params=params, timeout=60)
        if res.status_code == 200:
            return res.text
        else:
            print(f"[!] ZenRows API returned error {res.status_code}: {res.text[:150]}")
            return ""
    except Exception as e:
        print(f"[!] ZenRows API connection failed: {e}")
        return ""

# ==========================================
# 3. PORTAL SCRAPE & LOCAL FILTER LOGIC
# ==========================================
def scrape_portal_feed(portal_name, root_url, base_domain):
    print(f"[*] Fetching root stream from {portal_name}: {root_url}...")
    html = fetch_html_safe(root_url)
    if not html:
        print(f"[!] No HTML returned from {portal_name}.")
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings = []
    
    # Generic card matcher adapting to dynamic DOM class names across real estate portals
    cards = soup.find_all(["div", "article", "li"], class_=re.compile(r"(card|listing|property|item)", re.I))
    print(f"[*] Found {len(cards)} raw DOM cards on {portal_name}. Beginning local filtering...")

    for card in cards:
        try:
            text = card.get_text(separator=" ").strip()
            
            # --- LOCAL FILTER 1: CLUSTER CHECK ---
            matched_cluster = None
            for cluster in TARGET_CLUSTERS:
                if re.search(r"\b" + re.escape(cluster) + r"\b", text, re.I):
                    matched_cluster = cluster.upper()
                    break
            if not matched_cluster:
                continue # Discard out-of-target areas in memory

            # --- LOCAL FILTER 2: SIZE CHECK (< 1,200 SQFT) ---
            sqft_match = re.search(r"([\d,]+)\s*sqft", text, re.I)
            if not sqft_match:
                continue
            sqft = float(sqft_match.group(1).replace(",", ""))
            if sqft > MAX_SQFT_LIMIT or sqft < 100:
                continue # Discard oversized or invalid units

            # --- EXTRACT CORE METRICS ---
            link_elem = card.find("a", href=True)
            title = link_elem.get_text().strip() if link_elem else f"Retail Unit ({matched_cluster})"
            title = re.sub(r"\s+", " ", title) 
            
            link = link_elem["href"] if link_elem else root_url
            if link.startswith("/"):
                link = base_domain + link

            price_match = re.search(r"\$\s*([\d,]+)", text)
            price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

            listing_id = f"{portal_name[:2].upper()}_{re.sub(r'[^a-zA-Z0-9]', '', title)[:25]}_{int(sqft)}"

            listings.append({
                "id": listing_id,
                "portal": portal_name,
                "cluster": matched_cluster,
                "title": title[:60], 
                "sqft": sqft,
                "price": price,
                "link": link
            })
        except Exception:
            continue

    print(f"[*] {portal_name}: Filtered down to {len(listings)} qualified expansion targets.")
    return listings

# ==========================================
# 4. ORCHESTRATION & TELEGRAM BROADCAST
# ==========================================
def main():
    # --- PRE-PRODUCTION DEBUG PING ---
    send_telegram_alert("🟢 **ZenRows Integration Test:** Multi-Portal Scraper initialized online.")
    # ---------------------------------

    seen_listings = load_seen_listings()
    
    # 1. Scrape CommercialGuru Root Retail Stream
    cg_units = scrape_portal_feed(
        portal_name="CommercialGuru",
        root_url="https://www.commercialguru.com.sg/retail-for-rent",
        base_domain="https://www.commercialguru.com.sg"
    )
    
    # 2. Scrape EdgeProp Root Commercial Stream
    ep_units = scrape_portal_feed(
        portal_name="EdgeProp",
        root_url="https://www.edgeprop.sg/commercial-for-rent",
        base_domain="https://www.edgeprop.sg"
    )

    all_units = cg_units + ep_units
    unseen_units = [u for u in all_units if u["id"] not in seen_listings]
    
    print(f"[*] Total combined new qualified units: {len(unseen_units)}")
    
    if not unseen_units:
        send_telegram_alert("ℹ️ **Scan Complete:** 0 new units matched the <1,200 sqft cluster criteria today.")
        print("[*] Pipeline finished cleanly.")
        return

    report_blocks = [
        "🏢 **ACER ACADEMY: MULTI-PORTAL EXPANSION INTEL** 🏢",
        f"*Scraped via ZenRows API • {len(unseen_units)} Qualified Units Found*",
        "---"
    ]

    for idx, unit in enumerate(unseen_units, 1):
        psf = round(unit["price"] / unit["sqft"], 2) if unit["price"] > 0 and unit["sqft"] > 0 else 0.0
        psf_display = f"${psf} PSF" if psf > 0 else "Ask for Price"
        psf_flag = " ⚠️ *(High PSF)*" if psf > MAX_PSF_THRESHOLD else ""

        lat, lon = get_onemap_data(unit["title"])
        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            if dist < 800:
                tag = "⚠️ **[HIGH CANNIBALIZATION RISK]**"
                verdict = f"Only **{int(dist)}m** from {nearest_branch} branch! Avoid unless relocating."
            elif dist > 2500:
                tag = "🌟 **[PRIME EXPANSION GAP]**"
                verdict = f"**{round(dist/1000, 1)}km** from nearest center ({nearest_branch}). Great territory coverage!"
            else:
                tag = "📍 **[VIABLE TARGET]**"
                verdict = f"Nearest branch: {nearest_branch} ({round(dist/1000, 1)}km away)."
        else:
            tag = "📍 **[NEW LISTING]**"
            verdict = "GPS lookup unavailable; verify distance to existing centers manually."

        block = (
            f"{tag}\n"
            f"**{idx}. {unit['title']}**\n"
            f"• **Portal:** {unit['portal']} | **Cluster:** {unit['cluster']}\n"
            f"• **Size:** {int(unit['sqft'])} sqft\n"
            f"• **Asking Rent:** ${unit['price']:,.2f}/mth | **{psf_display}**{psf_flag}\n"
            f"• **Strategic Verdict:** {verdict}\n"
            f"🔗 [View Listing on {unit['portal']}]({unit['link']})"
        )
        report_blocks.append(block)
        report_blocks.append("---")
        seen_listings.add(unit["id"])
        time.sleep(0.5)

    for i in range(0, len(report_blocks), 5):
        chunk = "\n\n".join(report_blocks[i:i+5])
        send_telegram_alert(chunk)
        time.sleep(1)

    save_seen_listings(seen_listings)
    print("[+] State saved. All portal alerts dispatched successfully!")

if __name__ == "__main__":
    main()
