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
# Using old test token as requested for testing
TELEGRAM_BOT_TOKEN = "8891294738:AAGOuTbxEhZe0Y0wBX0cOFFonFp5m_1bvdA"
TELEGRAM_CHAT_ID = "-1004306469919"
ZENROWS_API_KEY = "0a72b44b388084523647e4dce2f6787701a1fbd6"

STATE_FILE = "seen_hdb_listings.json"
MAX_SQFT_LIMIT = 1200.0
MAX_PSF_THRESHOLD = 15.0

# Target Clusters for Acer Academy
CLUSTER_NAMES = {
    "JURONG": "West Cluster", "CLEMENTI": "West Cluster", "BUKIT BATOK": "West Cluster", 
    "CHOA CHU KANG": "West Cluster", "BUKIT PANJANG": "West Cluster", "BOON LAY": "West Cluster",
    "TOA PAYOH": "Central Cluster", "BISHAN": "Central Cluster", "KALLANG": "Central Cluster", 
    "WHAMPOA": "Central Cluster", "QUEENSTOWN": "Central Cluster", "BUKIT MERAH": "Central Cluster", 
    "CENTRAL AREA": "Central Cluster", "NOVENA": "Central Cluster",
    "SERANGOON": "East / Northeast Cluster", "HOUGANG": "East / Northeast Cluster", 
    "SENGKANG": "East / Northeast Cluster", "PUNGGOL": "East / Northeast Cluster", 
    "TAMPINES": "East / Northeast Cluster", "BEDOK": "East / Northeast Cluster", 
    "PASIR RIS": "East / Northeast Cluster", "GEYLANG": "East / Northeast Cluster", 
    "KOVAN": "East / Northeast Cluster"
}

# 17 Existing Acer Academy Branches (Lat, Lon)
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

CACHED_PRIMARY_SCHOOLS = []

# ==========================================
# 2. HELPER & GEOCODING ENGINE
# ==========================================
def fetch_json_safe(url):
    """Routes OneMap API requests through ZenRows to bypass cloud data-center firewalls."""
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    params = {"url": url, "apikey": ZENROWS_API_KEY, "premium_proxy": "true"}
    try:
        res = requests.get(zenrows_endpoint, params=params, timeout=25)
        if res.status_code == 200:
            return json.loads(res.text)
    except Exception as e:
        print(f"[!] ZenRows JSON proxy fetch failed for {url}: {e}")
    return {}

def format_display_address(raw_address):
    """Separates building names and street numbers cleanly onto two lines."""
    addr = raw_address.strip()
    addr = re.sub(r'([a-zA-Z])(\d+[\sA-Za-z])', r'\1, \2', addr)
    if ',' in addr:
        parts = [p.strip() for p in addr.split(',', 1)]
        if len(parts[0]) > 2 and len(parts[1]) > 2:
            return f"**{parts[0]}**\n📍 {parts[1]}"
    return f"**{addr}**"

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  
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

def load_primary_schools_once():
    global CACHED_PRIMARY_SCHOOLS
    if CACHED_PRIMARY_SCHOOLS:
        return CACHED_PRIMARY_SCHOOLS
        
    print("[*] Downloading MOE Primary School dataset via ZenRows...")
    url = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=primaryschool"
    res = fetch_json_safe(url)
    
    if "SrchResults" in res:
        for item in res["SrchResults"][1:]:
            lat = item.get("LATITUDE") or item.get("lat") or item.get("Y")
            lon = item.get("LONGITUDE") or item.get("lng") or item.get("lon") or item.get("X")
            name = item.get("NAME") or item.get("Name") or "Primary School"
            if lat and lon:
                try:
                    CACHED_PRIMARY_SCHOOLS.append({
                        "name": str(name).strip(),
                        "lat": float(lat),
                        "lon": float(lon)
                    })
                except ValueError:
                    continue
        print(f"[+] Successfully cached {len(CACHED_PRIMARY_SCHOOLS)} MOE Primary Schools!")
    return CACHED_PRIMARY_SCHOOLS

def count_nearby_primary_schools(target_lat, target_lon, radius_meters=1500):
    schools = load_primary_schools_once()
    if not schools:
        return -1
    count = 0
    for school in schools:
        dist = calculate_haversine_distance(target_lat, target_lon, school["lat"], school["lon"])
        if dist <= radius_meters:
            count += 1
    return count

def get_robust_gps(address_string, raw_text="", cluster_key=""):
    queries_to_try = []

    postal_match = re.search(r'\b(?:S\(|S|Singapore\s*)?(\d{6})\b', raw_text, re.I)
    if postal_match:
        queries_to_try.append(postal_match.group(1))

    clean_addr = re.sub(r'#\d+-[a-zA-Z0-9/]+', '', address_string)
    clean_addr = re.sub(r'\b(Shop|Retail|Unit|#\S+)\b', ' ', clean_addr, flags=re.I)
    clean_addr = re.sub(r'\s+', ' ', clean_addr).strip()
    if len(clean_addr) > 5:
        queries_to_try.append(clean_addr)

    if cluster_key and cluster_key not in queries_to_try:
        queries_to_try.append(f"{cluster_key} Singapore")

    for query in queries_to_try:
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={query}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
        res = fetch_json_safe(url)
        if res.get("found", 0) > 0:
            result = res["results"][0]
            return float(result["LATITUDE"]), float(result["LONGITUDE"])
            
    return None, None

def load_price_ledger():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {item: 0.0 for item in data}
                return data
        except Exception:
            return {}
    return {}

def save_price_ledger(ledger_dict):
    with open(STATE_FILE, "w") as f:
        json.dump(ledger_dict, f, indent=2)

def send_telegram_alert(markdown_message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": markdown_message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    requests.post(url, json=payload)

# ==========================================
# 3. HDB PLACE2LEASE SCRAPER ENGINE
# ==========================================
def scrape_hdb_place2lease():
    print("[*] Connecting to HDB Place2Lease portal via ZenRows (with 6s JS render wait)...")
    url = "https://place2lease.hdb.gov.sg/public/"
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    
    # CRITICAL FIX: "wait": "6000" gives HDB's frontend 6 seconds to fetch and render dynamic tables
    params = {
        "url": url, 
        "apikey": ZENROWS_API_KEY, 
        "js_render": "true", 
        "premium_proxy": "true",
        "wait": "6000"
    }
    
    try:
        res = requests.get(zenrows_endpoint, params=params, timeout=60)
        if res.status_code != 200:
            print(f"[!] HDB portal returned status code: {res.status_code}")
            return []
        html = res.text
    except Exception as e:
        print(f"[!] Connection to HDB failed: {e}")
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings = []
    
    # Check multiple container types HDB uses for cards, tables, or grid lists
    rows = soup.find_all(["tr", "div", "li", "article"], class_=re.compile(r"(row|card|listing|property|item|datatable|grid)", re.I))
    print(f"[*] Found {len(rows)} potential DOM elements on HDB page. Applying Acer Academy filters...")

    for row in rows:
        try:
            text = row.get_text(separator=" ").strip()
            
            # Basic validation: must contain Singapore postal code regex or sizing keyword
            if "sqm" not in text.lower() and "sqft" not in text.lower() and "s(" not in text.lower():
                continue

            # 1. Cluster Match
            matched_key = None
            for cluster in CLUSTER_NAMES.keys():
                if re.search(r"\b" + re.escape(cluster) + r"\b", text, re.I):
                    matched_key = cluster
                    break
            if not matched_key:
                continue

            # 2. Size Match
            sqm_match = re.search(r"([\d\.]+)\s*sqm", text, re.I)
            sqft_match = re.search(r"([\d,]+)\s*sqft", text, re.I)
            
            if sqm_match:
                sqm = float(sqm_match.group(1))
                sqft = sqm * 10.7639
            elif sqft_match:
                sqft = float(sqft_match.group(1).replace(",", ""))
                sqm = sqft / 10.7639
            else:
                continue
                
            if sqft > MAX_SQFT_LIMIT or sqft < 100:
                print(f"[debug] Filtered out {matched_key} unit due to size: {int(sqft)} sqft")
                continue

            # 3. Trade Match (Widened net to catch open trade, education, retail, and commercial office)
            valid_trade = re.search(r"(open trade|education|tuition|enrichment|school|retail|specific trade|commercial|office)", text, re.I)
            if not valid_trade:
                print(f"[debug] Filtered out {matched_key} unit due to trade restriction.")
                continue

            # 4. Address & Price Extraction
            addr_match = re.search(r"([^\n]+S\(\d{6}\))", text)
            address = addr_match.group(1).strip() if addr_match else f"HDB Commercial Unit ({matched_key})"
            
            price_match = re.search(r"\$\s*([\d,]+\.?\d*)", text)
            price = float(price_match.group(1).replace(",", "")) if price_match else 0.0
            
            # Identify Sealed Tenders vs Live Bidding
            is_sealed_tender = ("price only" in text.lower() or "tender" in text.lower() or price == 0.0)

            listing_id = f"HDB_{re.sub(r'[^a-zA-Z0-9]', '', address)[:25]}_{int(sqft)}"

            listings.append({
                "id": listing_id,
                "portal": "HDB Place2Lease",
                "cluster_key": matched_key,
                "address": address,
                "sqft": sqft,
                "sqm": round(sqm),
                "price": price,
                "is_sealed": is_sealed_tender,
                "link": url,
                "raw_text": text
            })
        except Exception as e:
            continue

    # Deduplicate in case HDB table rows have wrapper divs
    unique_listings = {u["id"]: u for u in listings}.values()
    print(f"[*] HDB Place2Lease: Filtered down to {len(unique_listings)} unique qualified targets.")
    return list(unique_listings)

# ==========================================
# 4. ORCHESTRATION & TELEGRAM BROADCAST
# ==========================================
def main():
    send_telegram_alert("🟢 **System Test:** HDB Daily Price-Tracker initialized online.")

    load_primary_schools_once()
    price_ledger = load_price_ledger()
    
    all_units = scrape_hdb_place2lease()
    
    actionable_units = []
    for u in all_units:
        lid = u["id"]
        current_price = u["price"]
        
        if lid not in price_ledger:
            u["alert_type"] = "NEW_LISTING"
            actionable_units.append(u)
        elif current_price > price_ledger[lid] and current_price > 0 and not u["is_sealed"]:
            u["alert_type"] = "PRICE_INCREASE"
            u["old_price"] = price_ledger[lid]
            actionable_units.append(u)
            
        price_ledger[lid] = current_price

    print(f"[*] Total actionable HDB alerts today: {len(actionable_units)}")
    
    if not actionable_units:
        send_telegram_alert("ℹ️ **HDB Daily Scan:** Checked active properties. 0 new listings or bid jumps today.\n*(Note: HDB Place2Lease tables refresh dynamically during active E-Bidding and open tender windows).*")
        save_price_ledger(price_ledger)
        print("[*] Pipeline finished cleanly.")
        return

    report_blocks = [
        "🏢 **ACER ACADEMY: HDB DAILY INTEL** 🏢",
        f"*{len(actionable_units)} Actionable Updates Found*",
        "---"
    ]

    for idx, unit in enumerate(actionable_units, 1):
        if unit["is_sealed"] or unit["price"] == 0:
            price_display = "💰 **🔒 Sealed Tender** | *Price determined on submission*"
        else:
            psf = round(unit["price"] / unit["sqft"], 2)
            psf_flag = " ⚠️ *(Above Market)*" if psf > MAX_PSF_THRESHOLD else ""
            price_display = f"💰 **${unit['price']:,.0f} / mth** |  **${psf:.2f} PSF**{psf_flag}"

        lat, lon = get_robust_gps(unit["address"], raw_text=unit.get("raw_text", ""), cluster_key=unit["cluster_key"])
        display_address = format_display_address(unit['address'])

        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            schools_count = count_nearby_primary_schools(lat, lon)
            
            schools_line = f"**{schools_count} Primary Schools** within 1.5km" if schools_count != -1 else "*OneMap sync error*"
            buffer_line = f"**{round(dist/1000, 1)} km** to {nearest_branch}"
            if dist < 800:
                schools_line += " ⚠️ *(High Cannibalization)*"
        else:
            schools_line = "*GPS sync pending* (Manual check needed)"
            buffer_line = "*GPS sync pending*"

        if unit["alert_type"] == "PRICE_INCREASE":
            header_badge = f"📈 **LIVE BID INCREASE** *(Was ${unit['old_price']:,.0f}/mth)*"
        else:
            header_badge = "📍 **NEW HDB LEASE**"

        block = (
            f"{header_badge}\n"
            f"🏢 {display_address}\n"
            f"🏷️ Official HDB Lease ({unit['cluster_key'].title()} / {CLUSTER_NAMES[unit['cluster_key']]})\n\n"
            f"📐 **{int(unit['sqft']):,} sqft** ({unit['sqm']} m²)\n"
            f"{price_display}\n\n"
            f"📍 **Location & Catchment:**\n"
            f"• **Schools:** {schools_line}\n"
            f"• **Branch Buffer:** {buffer_line}\n\n"
            f"🔗 [Open HDB Portal]({unit['link']})"
        )
        report_blocks.append(block)
        report_blocks.append("---")
        time.sleep(0.1)

    for i in range(0, len(report_blocks), 3):
        chunk = "\n\n".join(report_blocks[i:i+3])
        send_telegram_alert(chunk)
        time.sleep(1)

    save_price_ledger(price_ledger)
    print("[+] Price ledger updated. All HDB alerts dispatched successfully!")

if __name__ == "__main__":
    main()
