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
MIN_SQFT_LIMIT = 400.0  # No maximum limit as per boss's directive
MAX_PSF_THRESHOLD = 15.0

# Estimated Private Market PSF by Region (Used for 35% Discount Guessing Game)
PRIVATE_MARKET_PSF = {
    "West Cluster": 10.00,
    "Central Cluster": 15.00,
    "East / Northeast Cluster": 12.00,
    "General Region": 12.00  # Fallback for new/unmapped HDB towns
}

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

# Highly precise map coordinates for accurate cannibalization buffers
EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4328, 103.8413), 
    "Admiralty Place (North)": (1.4403, 103.8009),
    "The Woodgrove (North)": (1.4312, 103.7844), 
    "Vista Point (North)": (1.4315, 103.7937),
    "Canberra Plaza (North)": (1.4434, 103.8299), 
    "Tampines West (East)": (1.3486, 103.9360),
    "Buangkok Square (East)": (1.3839, 103.8817), 
    "Aljunied Maths/Science (East)": (1.3195, 103.8833),
    "Aljunied Languages (East)": (1.3196, 103.8833), 
    "Elias Mall (East)": (1.3775, 103.9427),
    "Dawson (Central)": (1.2934, 103.8110), 
    "Depot Heights (Central)": (1.2811, 103.8084),
    "Tiong Bahru (Central)": (1.2864, 103.8269), 
    "Cantonment (Central)": (1.2759, 103.8402),
    "Commonwealth (Central)": (1.3023, 103.7992), 
    "Senja Heights (West)": (1.3860, 103.7607),
    "Greenridge (West)": (1.3855, 103.7663), 
    "Hong Kah (West)": (1.3496, 103.7208)
}

DEBUG_LOGS = []

def debug_log(msg):
    print(msg)
    DEBUG_LOGS.append(msg)

def send_telegram_alert(markdown_message):
    """Sends formatted alert messages to the configured Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID, 
        "text": markdown_message, 
        "parse_mode": "Markdown", 
        "disable_web_page_preview": True
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        debug_log(f"[!] Failed to send Telegram alert: {e}")

# ==========================================
# 2. LOCAL MEMORY DATABASE LOADER
# ==========================================
def load_school_db():
    """Robust local database loader with path fail-safes."""
    possible_paths = [
        "school_db.json",
        os.path.join(os.path.dirname(__file__), "school_db.json") if "__file__" in globals() else None
    ]
    for path in possible_paths:
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    schools = json.load(f)
                    if schools:
                        return schools
            except Exception as e:
                debug_log(f"[!] Warning reading '{path}': {e}")
                
    # Fallback just in case school_db.json is missing on the runner
    debug_log("[!] school_db.json missing. Using micro-fallback database.")
    return [
        {"name": "Nanyang Primary School", "lat": 1.3210, "lon": 103.8060, "level": "PRIMARY"},
        {"name": "Rulang Primary School", "lat": 1.3468, "lon": 103.7190, "level": "PRIMARY"},
        {"name": "Nan Hua Primary School", "lat": 1.3190, "lon": 103.7600, "level": "PRIMARY"},
        {"name": "United World College (East)", "lat": 1.3575, "lon": 103.9450, "level": "INTERNATIONAL"}
    ]

# ==========================================
# 3. CORE UTILITIES
# ==========================================
def fetch_json_safe(url, use_sg_proxy=False):
    """Fetches API data utilizing ZenRows Anti-Bot layer to bypass Cloudflare/HDB firewalls."""
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    params = {
        "url": url, 
        "apikey": ZENROWS_API_KEY, 
        "premium_proxy": "true",
        "antibot": "true" # Forces ZenRows to solve CAPTCHAs before returning API data
    }
    if use_sg_proxy: params["proxy_country"] = "sg"
    
    try:
        res = requests.get(zenrows_endpoint, params=params, timeout=45)
        if res.status_code == 200:
            text = res.text
            if text.strip().startswith("<"): 
                debug_log("[!] FATAL: ZenRows returned HTML. HDB's Firewall blocked the JSON API request!")
                return {}
            try:
                data = json.loads(text)
                debug_log(f"[+] API Hit Success! Keys retrieved: {list(data.keys())[:5]}")
                return data
            except Exception as e:
                debug_log(f"[!] Failed to parse JSON. Response preview: {text[:100]}")
                return {}
        else:
            debug_log(f"[!] Target URL returned HTTP {res.status_code}. Response preview: {res.text[:100]}")
    except Exception as e:
        debug_log(f"[!] Proxy connection failed for {url}: {e}")
    return {}

def deep_find(obj, *keys):
    target_keys = [k.lower() for k in keys]
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in target_keys and v is not None and str(v).strip() != "":
                return v
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                res = deep_find(v, *keys)
                if res is not None and str(res).strip() != "":
                    return res
    elif isinstance(obj, list):
        for item in obj:
            res = deep_find(item, *keys)
            if res is not None and str(res).strip() != "":
                return res
    return None

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

def count_local_schools(target_lat, target_lon, school_list, radius_meters=1500):
    """Instant local calculation: 0 API overhead and 100% immune to firewalls."""
    if not target_lat or not target_lon: return 0
    count = sum(1 for s in school_list if calculate_haversine_distance(target_lat, target_lon, s["lat"], s["lon"]) <= radius_meters)
    return count

def get_robust_gps(address_string, cluster_key=""):
    queries_to_try = []
    postal_match = re.search(r'\b(\d{6})\b', address_string)
    if postal_match: queries_to_try.append(postal_match.group(1))

    clean_addr = re.sub(r'#\d+-[a-zA-Z0-9/]+', '', address_string)
    clean_addr = re.sub(r'\b(Shop|Retail|Unit|HDB|Commercial|#\S+)\b', ' ', clean_addr, flags=re.I).strip()
    if len(clean_addr) > 5: queries_to_try.append(clean_addr)
    if cluster_key: queries_to_try.append(f"{cluster_key} Singapore")

    for query in queries_to_try:
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={query}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
        res = fetch_json_safe(url, use_sg_proxy=True)
        if res and res.get("found", 0) > 0:
            return float(res["results"][0]["LATITUDE"]), float(res["results"][0]["LONGITUDE"])
    return None, None

def format_display_address(raw_address):
    addr = raw_address.strip()
    addr = re.sub(r'([a-zA-Z])(\d+[\sA-Za-z])', r'\1, \2', addr)
    if ',' in addr:
        parts = [p.strip() for p in addr.split(',', 1)]
        if len(parts[0]) > 2 and len(parts[1]) > 2:
            return f"**{parts[0]}**\n📍 {parts[1]}"
    return f"**{addr}**"

# ==========================================
# 4. DATA PARSING & HARDSCRAPE DATE FALLBACK
# ==========================================
def format_hdb_date(date_val):
    val_str = str(date_val).strip()
    if not val_str or val_str.lower() in ["none", "e-bidding", "open", "null", "tba", "price only"]:
        return "TBA"

    try:
        if val_str.isdigit() or isinstance(date_val, (int, float)):
            ts = int(date_val)
            if ts < 1000000000: return "TBA"
            if ts > 9999999999: ts = ts / 1000
            return time.strftime("%d %b %Y, %I:%M %p", time.localtime(ts))
            
        if 'T' in val_str:
            clean_str = val_str.split('.')[0].replace('Z', '')
            dt = time.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
            return time.strftime("%d %b %Y, %I:%M %p", dt)
            
        if any(char.isdigit() for char in val_str) and len(val_str) > 5:
            return val_str
    except Exception: pass
    
    return "TBA"

def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, ' ', str(raw_html))

def extract_closing_date(item, item_id, link_path):
    # 1. Structured Data Scan
    keys_to_check = ["currentBidClosingDate", "tenderClosingDate", "closingDate", "tenderEndDate", "endDate", "closeDate"]
    for k in keys_to_check:
        raw = deep_find(item, k)
        if raw:
            formatted = format_hdb_date(raw)
            if formatted != "TBA": return formatted

    # 2. Hard-Scrape Fallback (with stripped HTML tags to bypass formatting traps)
    if item_id:
        debug_log(f"[*] Date hidden or non-chronological. Hard-scraping JS HTML for unit {item_id}...")
        try:
            page_url = f"https://place2lease.hdb.gov.sg/public/view-properties/true/{link_path}/{item_id}"
            zr = "https://api.zenrows.com/v1/"
            params = {"url": page_url, "apikey": ZENROWS_API_KEY, "premium_proxy": "true", "js_render": "true", "wait": "3000"}
            html_res = requests.get(zr, params=params, timeout=40)
            
            clean_text = clean_html(html_res.text)
            
            m1 = re.search(r'Tender closing on\s*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4}[,\s]+[0-9]{1,2}:[0-9]{2}:[0-9]{2}[a-zA-Z]{2})', clean_text, re.IGNORECASE)
            if m1: return m1.group(1).strip()
            
            m2 = re.search(r'Tender ends on\s*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4})', clean_text, re.IGNORECASE)
            if m2: return m2.group(1).strip()
        except Exception as e:
            debug_log(f"[!] HTML Scrape fallback failed for {item_id}: {e}")
            
    return "TBA"

# ==========================================
# 5. SCRAPER & FILTER LOOP
# ==========================================
def scrape_hdb_place2lease():
    debug_log("[*] Intercepting internal HDB JSON feed...")
    api_url = "https://place2lease.hdb.gov.sg/webservice-public/api/v1/tender-units/public/search-tender-units?page=1&pageSize=100&order=asc&orderProperty=lastPost.currentBidClosingDate&startIndex=0"
    
    payload = fetch_json_safe(api_url, use_sg_proxy=True)
    raw_units = []
    
    if not payload:
        debug_log("[!] Payload is completely empty. API blocked or timed out.")
        return []

    if isinstance(payload, list): 
        raw_units = payload
    elif isinstance(payload, dict):
        total_elements = payload.get("totalElements")
        if total_elements == 0:
            debug_log("[*] HDB API confirms totalElements = 0. There are LEGITIMATELY no active tenders right now.")
            return []
            
        for key in ["content", "results", "tenderUnits", "data", "list", "items"]:
            if key in payload and isinstance(payload[key], list): 
                raw_units = payload[key]
                break
        if not raw_units:
            for k, v in payload.items():
                if isinstance(v, dict):
                    for subkey in ["content", "results", "tenderUnits", "list", "items"]:
                        if subkey in v and isinstance(v[subkey], list): 
                            raw_units = v[subkey]
                            break
    
    if not raw_units:
        debug_log(f"[!] Could not extract property array from payload. Payload dump: {str(payload)[:150]}")
        return []

    debug_log(f"[+] Intercepted {len(raw_units)} raw properties. Applying filters...")
    listings = []

    for item in raw_units:
        try:
            item_text = json.dumps(item).lower()
            
            raw_full_address = deep_find(item, "address", "propertyAddress", "displayAddress", "locationAddress")
            if raw_full_address and len(str(raw_full_address)) > 5:
                full_address = str(raw_full_address).strip()
            else:
                block = str(deep_find(item, "blockNo", "block") or "").strip()
                street = str(deep_find(item, "streetName", "street") or "").strip()
                postal = str(deep_find(item, "postalCode", "postal") or "").strip()
                unit_no = str(deep_find(item, "unitNo", "unit") or "").strip()
                
                if block and street: full_address = f"Blk {block} {street}"
                elif block: full_address = f"Blk {block}"
                elif street: full_address = street
                else: full_address = f"HDB Commercial Unit"
                    
                if unit_no and unit_no != "None": full_address += f" #{unit_no}"
                if postal and postal != "None": full_address += f" S({postal})"
                
            matched_key = None
            for cluster in CLUSTER_NAMES.keys():
                if cluster.lower() in item_text:
                    matched_key = cluster
                    break
            if not matched_key:
                raw_town = deep_find(item, "townDescription", "town") or ""
                matched_key = str(raw_town).strip().title() if raw_town else "Unmapped Region"

            if full_address == "HDB Commercial Unit":
                full_address = f"HDB Commercial Unit ({matched_key})"

            sqm = 0.0
            for k in ["floorArea", "areaSqm", "allocatedArea", "area", "sqm"]:
                if k in item and item[k]:
                    try: 
                        sqm = float(item[k])
                        break
                    except: pass
            
            sqft = sqm * 10.7639
            if sqft < MIN_SQFT_LIMIT: continue

            valid_trade = re.search(r"(open trade|specific trade|shop|education|tuition|enrichment|school|retail|commercial|office)", item_text)
            if not valid_trade: continue
                
            raw_trade = deep_find(item, "tradeDescription", "allowableTrade", "tradeCategory", "trade")
            if raw_trade: trade_type = str(raw_trade).strip().title()
            elif valid_trade: trade_type = valid_trade.group(0).title()
            else: trade_type = "Not Specified"

            current_bid = deep_find(item, "currentBid", "highestBid", "tenderPrice", "price") or 0.0
            price = float(current_bid)
            
            tender_type = str(deep_find(item, "tenderType", "postType", "type") or "").lower()
            is_sealed = ("price only" in tender_type or "sealed" in tender_type or price == 0.0)

            unique_id = f"HDB_{re.sub(r'[^a-zA-Z0-9]', '', full_address)[:25]}_{int(sqft)}"
            
            item_id = str(deep_find(item, "id", "tenderUnitId", "propertyId", "unitId") or "")
            link_path = "ebid-unit-details" 
            if item_id and item_id != "None":
                direct_link = f"https://place2lease.hdb.gov.sg/public/view-properties/true/{link_path}/{item_id}"
            else:
                direct_link = "https://place2lease.hdb.gov.sg/public/"

            closing_date = extract_closing_date(item, item_id, link_path)

            listings.append({
                "id": unique_id,
                "portal": "HDB Place2Lease",
                "cluster_key": matched_key,
                "address": full_address,
                "sqft": sqft,
                "sqm": round(sqm),
                "price": price,
                "is_sealed": is_sealed,
                "trade_type": trade_type,
                "closing_date": closing_date,
                "link": direct_link
            })
        except Exception as e:
            debug_log(f"[!] Processing error on item: {e}")

    return listings

def load_price_ledger():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {}

def save_price_ledger(ledger_dict):
    with open(STATE_FILE, "w") as f: json.dump(ledger_dict, f, indent=2)

# ==========================================
# 6. ORCHESTRATION ENGINE
# ==========================================
def main():
    send_telegram_alert("🟢 **System Test:** Direct HDB API Pipeline live. Fetching active inventory...")
    
    price_ledger = load_price_ledger()
    school_list = load_school_db()
    all_units = scrape_hdb_place2lease()
    
    debug_log(f"[*] Found {len(all_units)} qualified active HDB properties.")
    
    if not all_units:
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
        
        if lid not in price_ledger: header_badge = "📍 **NEW HDB LEASE**"
        elif current_price > price_ledger.get(lid, 0.0) and current_price > 0 and not unit["is_sealed"]:
            header_badge = f"📈 **LIVE BID INCREASE** *(Was ${price_ledger[lid]:,.0f}/mth)*"
        else: header_badge = "📌 **ACTIVE HDB LEASE**"
            
        price_ledger[lid] = current_price

        # Guessing Game Calculations
        cluster_region = CLUSTER_NAMES.get(unit['cluster_key'], "General Region")
        est_private_psf = PRIVATE_MARKET_PSF.get(cluster_region, 12.0)
        hdb_psf_bid = est_private_psf * 0.65 
        est_monthly = hdb_psf_bid * unit['sqft']

        if unit["is_sealed"] or unit["price"] == 0:
            price_display = (
                f"💰 **🔒 Sealed Tender** (No upfront price listed)\n"
                f"💡 **Suggested Bid:** ~${est_monthly:,.0f} / mth (${hdb_psf_bid:.2f} PSF)\n"
                f"*(Based on ~35% discount from ${est_private_psf:.2f} private market avg)*"
            )
        else:
            psf = round(unit["price"] / unit["sqft"], 2)
            psf_flag = " ⚠️ *(Above Market)*" if psf > MAX_PSF_THRESHOLD else ""
            price_display = (
                f"💰 **${unit['price']:,.0f} / mth** | **${psf:.2f} PSF**{psf_flag}\n"
                f"💡 **Target Bid:** ~${est_monthly:,.0f} / mth (${hdb_psf_bid:.2f} PSF)\n"
                f"*(Based on ~35% discount from ${est_private_psf:.2f} private market avg)*"
            )

        lat, lon = get_robust_gps(unit["address"], cluster_key=unit["cluster_key"])
        display_address = format_display_address(unit['address'])

        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            schools_count = count_local_schools(lat, lon, school_list)
            
            schools_line = f"**{schools_count} Academic Institutions** within 1.5km" 
            buffer_line = f"**{round(dist/1000, 1)} km** to {nearest_branch}"
            if dist < 800: schools_line += " ⚠️ *(High Cannibalization)*"
        else:
            schools_line = "*GPS Resolution Missing* (Manual check required)"
            buffer_line = "*GPS Sync Pending*"

        warning_block = "⚠️ **ACTION REQUIRED:** Click the link below and expand \"Important Unit Conditions\" to verify no existing tuition/enrichment trades currently exist in this block."

        block = (
            f"{header_badge}\n"
            f"🏢 {display_address}\n"
            f"🏷️ Official HDB Lease ({unit['cluster_key'].title()} / {cluster_region})\n\n"
            f"📐 **{int(unit['sqft']):,} sqft** ({unit['sqm']} m²)\n"
            f"{price_display}\n\n"
            f"🛍️ **Trade Type:** {unit.get('trade_type', 'Not Specified')}\n"
            f"🗓️ **Tender Ends:** {unit.get('closing_date', 'TBA')}\n\n"
            f"📍 **Location & Local Catchment:**\n"
            f"• **Schools:** {schools_line}\n"
            f"• **Branch Buffer:** {buffer_line}\n\n"
            f"{warning_block}\n\n"
            f"🔗 [Find Out More]({unit['link']})"
        )
        report_blocks.append(block)
        report_blocks.append("---")

    for i in range(0, len(report_blocks), 2):
        chunk = "\n\n".join(report_blocks[i:i+2])
        send_telegram_alert(chunk)
        time.sleep(1)

    save_price_ledger(price_ledger)
    debug_log("[+] Pipeline finished successfully.")

if __name__ == "__main__":
    main()
