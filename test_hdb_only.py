import os
import re
import json
import math
import time
import requests

# ==========================================
# 1. CONFIGURATION & TEST CREDENTIALS
# ==========================================
TELEGRAM_BOT_TOKEN = "8891294738:AAGOuTbxEhZe0Y0wBX0cOFFonFp5m_1bvdA"
TELEGRAM_CHAT_ID = "-1004306469919"
ZENROWS_API_KEY = "0a72b44b388084523647e4dce2f6787701a1fbd6"

STATE_FILE = "seen_hdb_listings.json"
MAX_SQFT_LIMIT = 1200.0
MAX_PSF_THRESHOLD = 15.0

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

EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4331, 103.8405), "Admiralty Place (North)": (1.4402, 103.8008),
    "The Woodgrove (North)": (1.4310, 103.7845), "Vista Point (North)": (1.4300, 103.7920),
    "Canberra Plaza (North)": (1.4430, 103.8300), "Tampines West (East)": (1.3503, 103.9358),
    "Buangkok Square (East)": (1.3838, 103.8820), "Aljunied Maths/Science (East)": (1.3193, 103.8831),
    "Aljunied Languages (East)": (1.3195, 103.8833), "Elias Mall (East)": (1.3780, 103.9430),
    "Dawson (Central)": (1.2950, 103.8110), "Depot Heights (Central)": (1.2806, 103.8080),
    "Tiong Bahru (Central)": (1.2865, 103.8260), "Cantonment (Central)": (1.2755, 103.8400),
    "Commonwealth (Central)": (1.3030, 103.7990), "Senja Heights (West)": (1.3850, 103.7610),
    "Greenridge (West)": (1.3860, 103.7710), "Hong Kah (West)": (1.3520, 103.7250)
}

CACHED_PRIMARY_SCHOOLS = []
DEBUG_LOGS = []

def debug_log(msg):
    """Stores logs so they can be sent directly to Telegram if the script fails."""
    print(msg)
    DEBUG_LOGS.append(msg)

# ==========================================
# 2. CORE UTILITIES
# ==========================================
def fetch_json_safe(url, use_sg_proxy=False):
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    params = {"url": url, "apikey": ZENROWS_API_KEY, "premium_proxy": "true"}
    if use_sg_proxy: params["proxy_country"] = "sg"
    
    try:
        res = requests.get(zenrows_endpoint, params=params, timeout=30)
        if res.status_code == 200:
            text = res.text
            if text.strip().startswith("<"):
                debug_log("[!] ZenRows returned HTML. HDB Firewall is blocking the API request!")
                return {}
            return json.loads(text)
        else:
            debug_log(f"[!] Target URL returned status code: {res.status_code}")
    except Exception as e:
        debug_log(f"[!] Proxy connection failed for {url}: {e}")
    return {}

def format_display_address(raw_address):
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
    if CACHED_PRIMARY_SCHOOLS: return CACHED_PRIMARY_SCHOOLS
    url = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=primaryschool"
    res = fetch_json_safe(url)
    if "SrchResults" in res:
        for item in res["SrchResults"][1:]:
            lat = item.get("LATITUDE") or item.get("lat") or item.get("Y")
            lon = item.get("LONGITUDE") or item.get("lng") or item.get("lon") or item.get("X")
            name = item.get("NAME") or item.get("Name") or "Primary School"
            if lat and lon:
                try: CACHED_PRIMARY_SCHOOLS.append({"name": str(name).strip(), "lat": float(lat), "lon": float(lon)})
                except ValueError: continue
    return CACHED_PRIMARY_SCHOOLS

def count_nearby_primary_schools(target_lat, target_lon, radius_meters=1500):
    schools = load_primary_schools_once()
    if not schools: return -1
    count = sum(1 for s in schools if calculate_haversine_distance(target_lat, target_lon, s["lat"], s["lon"]) <= radius_meters)
    return count

def get_robust_gps(address_string, cluster_key=""):
    queries_to_try = []
    postal_match = re.search(r'\b(\d{6})\b', address_string)
    if postal_match: queries_to_try.append(postal_match.group(1))

    clean_addr = re.sub(r'#\d+-[a-zA-Z0-9/]+', '', address_string)
    clean_addr = re.sub(r'\b(Shop|Retail|Unit|#\S+)\b', ' ', clean_addr, flags=re.I).strip()
    if len(clean_addr) > 5: queries_to_try.append(clean_addr)
    if cluster_key and cluster_key not in queries_to_try: queries_to_try.append(f"{cluster_key} Singapore")

    for query in queries_to_try:
        res = fetch_json_safe(f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={query}&returnGeom=Y&getAddrDetails=Y&pageNum=1")
        if res.get("found", 0) > 0:
            return float(res["results"][0]["LATITUDE"]), float(res["results"][0]["LONGITUDE"])
    return None, None

def load_price_ledger():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {}

def save_price_ledger(ledger_dict):
    with open(STATE_FILE, "w") as f: json.dump(ledger_dict, f, indent=2)

def send_telegram_alert(markdown_message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": markdown_message, "parse_mode": "Markdown", "disable_web_page_preview": True}
    requests.post(url, json=payload)

# ==========================================
# 3. DIRECT HDB API INTERCEPTION
# ==========================================
def extract_list_from_payload(data):
    """Hunts deeply for the array of properties regardless of what HDB named the keys."""
    if isinstance(data, list): return data
    if isinstance(data, dict):
        for key in ["content", "results", "tenderUnits", "data", "list", "items"]:
            if key in data and isinstance(data[key], list): return data[key]
        for k, v in data.items():
            if isinstance(v, dict):
                for subkey in ["content", "results", "tenderUnits", "list", "items"]:
                    if subkey in v and isinstance(v[subkey], list): return v[subkey]
    return []

def scrape_hdb_place2lease():
    debug_log("[*] Intercepting internal HDB JSON feed...")
    api_url = "https://place2lease.hdb.gov.sg/webservice-public/api/v1/tender-units/public/search-tender-units?page=1&pageSize=100&order=asc&orderProperty=lastPost.currentBidClosingDate&startIndex=0"
    
    payload = fetch_json_safe(api_url, use_sg_proxy=True)
    raw_units = extract_list_from_payload(payload)
        
    if not raw_units:
        debug_log(f"[!] No raw properties found in payload. Extracted Keys: {list(payload.keys())[:10] if isinstance(payload, dict) else 'None'}")
        return []

    debug_log(f"[+] Intercepted {len(raw_units)} raw properties. Applying filters...")
    listings = []

    for item in raw_units:
        try:
            item_text = json.dumps(item).lower()
            
            block = str(item.get("blockNo", "")).strip()
            street = str(item.get("streetName", "")).strip()
            postal = str(item.get("postalCode", "")).strip()
            unit_no = str(item.get("unitNo", "")).strip()
            
            full_address = f"Blk {block} {street}"
            if unit_no and unit_no != "None": full_address += f" #{unit_no}"
            if postal and postal != "None": full_address += f" S({postal})"
                
            # 1. Cluster Verification
            matched_key = None
            for cluster in CLUSTER_NAMES.keys():
                if cluster.lower() in item_text:
                    matched_key = cluster
                    break
            if not matched_key:
                debug_log(f"[drop] {full_address}: No valid cluster/town found.")
                continue

            # 2. Size Verification
            sqm = 0.0
            for k in ["floorArea", "areaSqm", "allocatedArea", "area", "sqm"]:
                if k in item and item[k]:
                    try: 
                        sqm = float(item[k])
                        break
                    except: pass
            
            sqft = sqm * 10.7639
            if sqft > MAX_SQFT_LIMIT or sqft < 100:
                debug_log(f"[drop] {full_address}: Size {int(sqft)} sqft exceeds limit.")
                continue

            # 3. Trade Verification
            valid_trade = re.search(r"(open trade|specific trade|shop|education|tuition|enrichment|school|retail|commercial|office)", item_text)
            if not valid_trade:
                debug_log(f"[drop] {full_address}: Trade type restricted.")
                continue

            # 4. Pricing Logic
            current_bid = item.get("currentBid") or item.get("highestBid") or item.get("tenderPrice") or 0.0
            price = float(current_bid)
            
            is_sealed = ("price only" in str(item.get("tenderType", "")).lower() or 
                         "sealed" in str(item.get("postType", "")).lower() or 
                         price == 0.0)

            unique_id = f"HDB_{re.sub(r'[^a-zA-Z0-9]', '', full_address)[:25]}_{int(sqft)}"

            listings.append({
                "id": unique_id,
                "portal": "HDB Place2Lease",
                "cluster_key": matched_key,
                "address": full_address,
                "sqft": sqft,
                "sqm": round(sqm),
                "price": price,
                "is_sealed": is_sealed,
                "link": "https://place2lease.hdb.gov.sg/public/"
            })
        except Exception as e:
            debug_log(f"[!] Processing error on item: {e}")

    return listings

# ==========================================
# 4. ORCHESTRATION ENGINE
# ==========================================
def main():
    send_telegram_alert("🟢 **System Test:** Direct HDB API Pipeline live. Fetching active inventory...")
    
    price_ledger = load_price_ledger()
    all_units = scrape_hdb_place2lease()
    
    debug_log(f"[*] Found {len(all_units)} qualified active HDB properties today.")
    
    if not all_units:
        # Flattened error message to completely prevent multiline syntax errors!
        log_text = "\n".join(DEBUG_LOGS[-15:])
        error_msg = f"ℹ️ **HDB Feed Diagnostic:** 0 properties matched criteria.\n\n**Auto-Debug Logs:**\n```text\n{log_text}\n```"
        send_telegram_alert(error_msg)
        return

    report_blocks = [
        "🏢 **ACER ACADEMY: ACTIVE HDB INVENTORY** 🏢",
        f"*{len(all_units)} Target Matches Currently Open for Bidding/Tender*",
        "---"
    ]

    for unit in all_units:
        lid = unit["id"]
        current_price = unit["price"]
        
        if lid not in price_ledger:
            header_badge = "📍 **NEW HDB LEASE**"
        elif current_price > price_ledger.get(lid, 0.0) and current_price > 0 and not unit["is_sealed"]:
            header_badge = f"📈 **LIVE BID INCREASE** *(Was ${price_ledger[lid]:,.0f}/mth)*"
        else:
            header_badge = "📌 **ACTIVE HDB LEASE**"
            
        price_ledger[lid] = current_price

        if unit["is_sealed"] or unit["price"] == 0:
            price_display = "💰 **🔒 Sealed Tender** | *Price determined on submission*"
        else:
            psf = round(unit["price"] / unit["sqft"], 2)
            psf_flag = " ⚠️ *(Above Market)*" if psf > MAX_PSF_THRESHOLD else ""
            price_display = f"💰 **${unit['price']:,.0f} / mth** |  **${psf:.2f} PSF**{psf_flag}"

        lat, lon = get_robust_gps(unit["address"], cluster_key=unit["cluster_key"])
        display_address = format_display_address(unit['address'])

        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            schools_count = count_nearby_primary_schools(lat, lon)
            
            schools_line = f"**{schools_count} Primary Schools** within 1.5km" if schools_count != -1 else "*Catchment lookup down*"
            buffer_line = f"**{round(dist/1000, 1)} km** to {nearest_branch}"
            if dist < 800: schools_line += " ⚠️ *(High Cannibalization)*"
        else:
            schools_line = "*GPS Resolution Missing* (Manual check required)"
            buffer_line = "*GPS Sync Pending*"

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

    for i in range(0, len(report_blocks), 3):
        chunk = "\n\n".join(report_blocks[i:i+3])
        send_telegram_alert(chunk)
        time.sleep(1)

    save_price_ledger(price_ledger)
    debug_log("[+] Pipeline finished successfully.")

if __name__ == "__main__":
    main()
