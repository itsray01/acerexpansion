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
MIN_SQFT_LIMIT = 400.0 # No maximum limit as per new directive
MAX_PSF_THRESHOLD = 15.0

# Estimated Private Market PSF by Region (Used for 35% Discount Guessing Game)
PRIVATE_MARKET_PSF = {
    "West Cluster": 10.00,
    "Central Cluster": 15.00,
    "East / Northeast Cluster": 12.00,
    "General Region": 12.00 # Fallback for new/unmapped HDB towns
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

# Updated with highly precise map coordinates for accurate cannibalization buffers
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

CACHED_PRIMARY_SCHOOLS = []
DEBUG_LOGS = []

def debug_log(msg):
    """Stores logs so they can be sent directly to Telegram if the script fails."""
    print(msg)
    DEBUG_LOGS.append(msg)

# ==========================================
# 2. CORE UTILITIES & DEEP SEARCH
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
                debug_log("[!] ZenRows returned HTML. Firewall is blocking the API request!")
                return {}
            return json.loads(text)
        else:
            debug_log(f"[!] Target URL returned status code: {res.status_code}")
    except Exception as e:
        debug_log(f"[!] Proxy connection failed for {url}: {e}")
    return {}

def deep_find(obj, *keys):
    """Recursively searches for keys in a nested JSON object to defeat nested HDB data."""
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

def format_hdb_date(date_val):
    if not date_val or str(date_val).lower() == "none":
        return "TBA"
    try:
        # Handle Unix Timestamps safely
        if isinstance(date_val, (int, float)) or (isinstance(date_val, str) and str(date_val).isdigit()):
            ts = int(date_val)
            if ts < 1000000000: 
                # 1 Billion seconds = Sept 2001. Prevents small HDB IDs from becoming 1970 dates!
                return "TBA" 
            if ts > 9999999999: # Convert milliseconds to seconds
                ts = ts / 1000
            dt = time.localtime(ts)
            return time.strftime("%d %b %Y, %I:%M %p", dt)
            
        # Handle standard string formats (e.g. 15 Jul 2026 or ISO formats)
        date_str = str(date_val).strip()
        if 'T' in date_str and ('Z' in date_str or '+' in date_str):
            clean_str = date_str.split('.')[0].replace('Z', '')
            dt = time.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
            return time.strftime("%d %b %Y, %I:%M %p", dt)
        
        return date_str
    except Exception:
        return str(date_val)

def extract_closing_date(item, item_id, link_path):
    """Bulletproof date extractor: Checks API keys, runs safe dynamic scans, and falls back to JS scraping."""
    # 1. Check strict known explicit keys
    raw = deep_find(item, "currentBidClosingDate", "tenderClosingDate", "closingDate", "tenderEndDate", "endDate", "biddingEndDate", "closeDate")
    if raw:
        formatted = format_hdb_date(raw)
        if formatted != "TBA": return formatted

    # 2. Dynamic safe scan (ignoring ID fields to prevent 1970 bug)
    def scan_for_date_keys(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                if kl in ['id', 'tenderunitid', 'propertyid', 'unitid', 'batchid', 'townid', 'clusterid', 'zoneid', 'price']:
                    continue
                if ("date" in kl or "close" in kl or "end" in kl or "time" in kl) and isinstance(v, (str, int, float)):
                    if str(v).strip() not in ["None", "", "0", "0.0"]:
                        if isinstance(v, (int, float)) or str(v).isdigit():
                            if int(v) > 1000000000: return v
                        else:
                            return v
            for v in obj.values():
                if isinstance(v, (dict, list)):
                    res = scan_for_date_keys(v)
                    if res: return res
        elif isinstance(obj, list):
            for i in obj:
                res = scan_for_date_keys(i)
                if res: return res
        return None
        
    raw_fallback = scan_for_date_keys(item)
    if raw_fallback:
        formatted = format_hdb_date(raw_fallback)
        if formatted != "TBA": return formatted

    # 3. Last Resort: ZenRows Headless Browser HTML Scrape
    if item_id:
        debug_log(f"[*] Date hidden. Hard-scraping JS HTML for unit {item_id}...")
        try:
            page_url = f"https://place2lease.hdb.gov.sg/public/view-properties/true/{link_path}/{item_id}"
            zr = "https://api.zenrows.com/v1/"
            # js_render=true forces ZenRows to wait for HDB's javascript timer to load
            params = {"url": page_url, "apikey": ZENROWS_API_KEY, "premium_proxy": "true", "js_render": "true", "wait": "3000"}
            html_res = requests.get(zr, params=params, timeout=40)
            
            # Regex Match: "Tender closing on 25 August 2026, 10:00:00am"
            m1 = re.search(r'Tender closing on\s*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4}[,\s]+[0-9]{1,2}:[0-9]{2}:[0-9]{2}[a-zA-Z]{2})', html_res.text, re.IGNORECASE)
            if m1: return m1.group(1).strip()
            
            # Regex Match: "Tender ends on 15 Jul 2026"
            m2 = re.search(r'Tender ends on\s*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4})', html_res.text, re.IGNORECASE)
            if m2: return m2.group(1).strip()
        except Exception as e:
            debug_log(f"[!] HTML Scrape fallback failed for {item_id}: {e}")
            
    return "TBA"

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

def process_school_payload(res):
    """Helper to extract schools from OneMap payload."""
    schools = []
    if "SrchResults" in res:
        for item in res["SrchResults"][1:]:
            lat = item.get("LATITUDE") or item.get("lat") or item.get("Y")
            lon = item.get("LONGITUDE") or item.get("lng") or item.get("lon") or item.get("X")
            name = item.get("NAME") or item.get("Name") or "Primary School"
            if lat and lon:
                try: schools.append({"name": str(name).strip(), "lat": float(lat), "lon": float(lon)})
                except ValueError: continue
    return schools

def load_schools_osm_fallback():
    """Unbreakable Tertiary Fallback using OpenStreetMap's Overpass Bounding Box if OneMap goes down."""
    debug_log("[*] Engaging OpenStreetMap Overpass API fallback for school catchments...")
    try:
        # Bounding Box specifically for Singapore (Lat/Lon range)
        query = """
        [out:json][timeout:15];
        (
          node["amenity"="school"]["name"~"Primary",i](1.156, 103.565, 1.483, 104.130);
          way["amenity"="school"]["name"~"Primary",i](1.156, 103.565, 1.483, 104.130);
        );
        out center;
        """
        res = requests.get("https://overpass-api.de/api/interpreter", params={'data': query}, timeout=15)
        if res.status_code == 200:
            schools = []
            for el in res.json().get("elements", []):
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")
                name = el.get("tags", {}).get("name", "Primary School")
                if lat and lon:
                    schools.append({"name": name, "lat": float(lat), "lon": float(lon)})
            debug_log(f"[+] OSM Fallback successful: Extracted {len(schools)} primary schools.")
            return schools
    except Exception as e:
        debug_log(f"[!] OSM Fallback failed: {e}")
    return []

def load_primary_schools_once():
    """Triple-Fetch mechanism to guarantee school catchments survive API timeouts."""
    global CACHED_PRIMARY_SCHOOLS
    if CACHED_PRIMARY_SCHOOLS: return CACHED_PRIMARY_SCHOOLS
    
    url = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=primaryschool"
    
    # Attempt 1: Direct Request with full spoofed browser headers
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.onemap.gov.sg/",
            "Accept": "application/json, text/plain, */*"
        }
        direct_res = requests.get(url, headers=headers, timeout=10)
        if direct_res.status_code == 200:
            CACHED_PRIMARY_SCHOOLS = process_school_payload(direct_res.json())
            if CACHED_PRIMARY_SCHOOLS:
                return CACHED_PRIMARY_SCHOOLS
    except Exception:
        pass
        
    # Attempt 2: ZenRows SG Proxy Request
    res = fetch_json_safe(url, use_sg_proxy=True) 
    CACHED_PRIMARY_SCHOOLS = process_school_payload(res)
    if CACHED_PRIMARY_SCHOOLS:
        return CACHED_PRIMARY_SCHOOLS
        
    # Attempt 3: OpenStreetMap Overpass Ultimate Fallback
    CACHED_PRIMARY_SCHOOLS = load_schools_osm_fallback()
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
    clean_addr = re.sub(r'\b(Shop|Retail|Unit|HDB|Commercial|#\S+)\b', ' ', clean_addr, flags=re.I).strip()
    if len(clean_addr) > 5: queries_to_try.append(clean_addr)
    
    if cluster_key: queries_to_try.append(f"{cluster_key} Singapore")

    for query in queries_to_try:
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={query}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
        res = fetch_json_safe(url, use_sg_proxy=True)
        if res and res.get("found", 0) > 0:
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
            
            # Robust Address Construction utilizing deep_find
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
                
            # 1. Cluster Verification
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

            # 2. Size Verification (400 sqft minimum)
            sqm = 0.0
            for k in ["floorArea", "areaSqm", "allocatedArea", "area", "sqm"]:
                if k in item and item[k]:
                    try: 
                        sqm = float(item[k])
                        break
                    except: pass
            
            sqft = sqm * 10.7639
            if sqft < MIN_SQFT_LIMIT:
                continue

            # 3. Trade Verification
            valid_trade = re.search(r"(open trade|specific trade|shop|education|tuition|enrichment|school|retail|commercial|office)", item_text)
            if not valid_trade:
                continue
                
            # Deep hunt for Trade Type with regex fallback
            raw_trade = deep_find(item, "tradeDescription", "allowableTrade", "tradeCategory", "trade")
            if raw_trade:
                trade_type = str(raw_trade).strip().title()
            elif valid_trade:
                trade_type = valid_trade.group(0).title()
            else:
                trade_type = "Not Specified"

            # 4. Pricing & Details ID extraction
            current_bid = deep_find(item, "currentBid", "highestBid", "tenderPrice", "price") or 0.0
            price = float(current_bid)
            
            tender_type = str(deep_find(item, "tenderType", "postType", "type") or "").lower()
            is_sealed = ("price only" in tender_type or "sealed" in tender_type or price == 0.0)

            unique_id = f"HDB_{re.sub(r'[^a-zA-Z0-9]', '', full_address)[:25]}_{int(sqft)}"
            
            # 5. Build explicit Path based on User Discovery ('ebid-unit-details' covers mostly everything now)
            item_id = str(deep_find(item, "id", "tenderUnitId", "propertyId", "unitId") or "")
            link_path = "ebid-unit-details" # Default to this as per your manual URL test!
            
            if item_id and item_id != "None":
                direct_link = f"https://place2lease.hdb.gov.sg/public/view-properties/true/{link_path}/{item_id}"
            else:
                direct_link = "https://place2lease.hdb.gov.sg/public/"

            # 6. Extract Closing Date (Will fall back to Hard Scraping if needed!)
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

# ==========================================
# 4. ORCHESTRATION ENGINE
# ==========================================
def main():
    send_telegram_alert("🟢 **System Test:** Direct HDB API Pipeline live. Fetching active inventory...")
    
    price_ledger = load_price_ledger()
    all_units = scrape_hdb_place2lease()
    
    debug_log(f"[*] Found {len(all_units)} qualified active HDB properties today.")
    
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
        
        if lid not in price_ledger:
            header_badge = "📍 **NEW HDB LEASE**"
        elif current_price > price_ledger.get(lid, 0.0) and current_price > 0 and not unit["is_sealed"]:
            header_badge = f"📈 **LIVE BID INCREASE** *(Was ${price_ledger[lid]:,.0f}/mth)*"
        else:
            header_badge = "📌 **ACTIVE HDB LEASE**"
            
        price_ledger[lid] = current_price

        # Guessing Game Calculations
        cluster_region = CLUSTER_NAMES.get(unit['cluster_key'], "General Region")
        est_private_psf = PRIVATE_MARKET_PSF.get(cluster_region, 12.0)
        hdb_psf_bid = est_private_psf * 0.65 # 35% discount calculation
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
            schools_count = count_nearby_primary_schools(lat, lon)
            
            schools_line = f"**{schools_count} Primary Schools** within 1.5km" if schools_count != -1 else "*Catchment lookup down*"
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
            f"📍 **Location & Catchment:**\n"
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
