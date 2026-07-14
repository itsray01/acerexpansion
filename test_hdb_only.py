import os
import re
import json
import math
import time
import csv
import requests
import pandas as pd

# ==========================================
# 1. CONFIGURATION & SECRETS  
# ==========================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Your Ziny Proxy Credentials injected from GitHub Secrets
PROXY_HOST = os.getenv("PROXY_HOST")
PROXY_PORT = os.getenv("PROXY_PORT")
PROXY_USER = os.getenv("PROXY_USER")
PROXY_PASS = os.getenv("PROXY_PASS")

STATE_FILE = "seen_hdb_listings.json"
MIN_SQFT_LIMIT = 400.0  

# Default CSV file path (Will be downloaded from GitHub on the fly)
MARKET_DATA_FILE = "sg_commercial_rent_listings_psf_sorted.csv"

# Trigger "Above Market" warning
MAX_PSF_THRESHOLD = 20.0

# 2026 Regional Baselines if a specific location is missing in the CSV
REGIONAL_FALLBACK_PSF = {
    "West Cluster": 15.00,             # OCR Suburban (Jurong, Clementi, CCK)
    "Central Cluster": 25.00,          # RCR City Fringe (Toa Payoh, Bishan, Queenstown)
    "East / Northeast Cluster": 16.00, # OCR Suburban (Tampines, Sengkang)
    "General Region": 16.00            # Fallback
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

EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4328, 103.8413), "Admiralty Place (North)": (1.4403, 103.8009),
    "The Woodgrove (North)": (1.4312, 103.7844), "Vista Point (North)": (1.4315, 103.7937),
    "Canberra Plaza (North)": (1.4434, 103.8299), "Tampines West (East)": (1.3486, 103.9360),
    "Buangkok Square (East)": (1.3839, 103.8817), "Aljunied Maths/Science (East)": (1.3195, 103.8833),
    "Aljunied Languages (East)": (1.3196, 103.8833), "Elias Mall (East)": (1.3775, 103.9427),
    "Dawson (Central)": (1.2934, 103.8110), "Depot Heights (Central)": (1.2811, 103.8084),
    "Tiong Bahru (Central)": (1.2864, 103.8269), "Cantonment (Central)": (1.2759, 103.8402),
    "Commonwealth (Central)": (1.3023, 103.7992), "Senja Heights (West)": (1.3860, 103.7607),
    "Greenridge (West)": (1.3855, 103.7663), "Hong Kah (West)": (1.3496, 103.7208)
}

DEBUG_LOGS = []

def debug_log(msg):
    print(msg)
    DEBUG_LOGS.append(msg)

def send_telegram_alert(markdown_message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        debug_log("[!] Telegram credentials missing from environment.")
        return
        
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

def get_proxies():
    """Constructs the standard proxy dictionary for requests from your env variables."""
    if PROXY_HOST and PROXY_PORT:
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        return {
            "http": proxy_url,
            "https": proxy_url
        }
    return None

def fetch_latest_commercial_data():
    """Pulls the pristine sorted dataset directly from your GitHub repository."""
    debug_log("[*] Downloading latest market dataset from GitHub repository...")
    url = "https://raw.githubusercontent.com/itsray01/acerexpansion/main/sg_commercial_rent_listings_psf_sorted.csv"
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            with open(MARKET_DATA_FILE, 'wb') as f:
                f.write(response.content)
            debug_log("[+] Successfully downloaded sg_commercial_rent_listings_psf_sorted.csv")
        else:
            debug_log(f"[!] GitHub raw file fetch failed. HTTP Status: {response.status_code}")
    except Exception as e:
        debug_log(f"[!] Error fetching CSV from GitHub: {e}")

def load_school_db():
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
                
    debug_log("[!] school_db.json missing. Using micro-fallback database.")
    return [
        {"name": "Nanyang Primary School", "lat": 1.3210, "lon": 103.8060, "level": "PRIMARY"},
        {"name": "Rulang Primary School", "lat": 1.3468, "lon": 103.7190, "level": "PRIMARY"},
        {"name": "Nan Hua Primary School", "lat": 1.3190, "lon": 103.7600, "level": "PRIMARY"},
        {"name": "United World College (East)", "lat": 1.3575, "lon": 103.9450, "level": "INTERNATIONAL"}
    ]

def lookup_market_psf(project_name, cluster_key):
    """
    Looks up the actual PSF for the given location using the reference sorted CSV file.
    If the project/location matches entries, it computes a hyper-localized median PSF. 
    Otherwise, it gracefully switches to falls back.
    """
    if not os.path.exists(MARKET_DATA_FILE):
        debug_log(f"[*] Reference file {MARKET_DATA_FILE} not found. Reverting to regional baseline.")
        cluster_region = CLUSTER_NAMES.get(cluster_key, "General Region")
        return REGIONAL_FALLBACK_PSF.get(cluster_region, 16.0), cluster_region, False

    try:
        matching_psfs = []
        project_normalized = str(project_name).strip().lower()
        
        with open(MARKET_DATA_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_project = str(row.get("Project", "")).strip().lower()
                row_address = str(row.get("Address", "")).strip().lower()
                
                if (project_normalized in row_project) or (row_project in project_normalized) or (project_normalized in row_address):
                    try:
                        psf_val = float(row.get("PSF", 0.0))
                        if psf_val > 0.1:
                            matching_psfs.append(psf_val)
                    except ValueError:
                        continue
                        
        if matching_psfs:
            matching_psfs.sort()
            mid = len(matching_psfs) // 2
            median_psf = (matching_psfs[mid] + matching_psfs[~mid]) / 2.0
            debug_log(f"[+] Found {len(matching_psfs)} direct market database matches for '{project_name}'. Calculated Localized Median: ${median_psf:.2f} PSF.")
            return median_psf, "Direct Matching (CSV Data Source)", True

    except Exception as e:
        debug_log(f"[!] Error reading market dataset: {e}")

    # Regional matching fallback inside the CSV
    try:
        cluster_psfs = []
        cluster_normalized = str(cluster_key).strip().lower()
        
        with open(MARKET_DATA_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_address = str(row.get("Address", "")).strip().lower()
                if cluster_normalized in row_address:
                    try:
                        psf_val = float(row.get("PSF", 0.0))
                        if psf_val > 0.1:
                            cluster_psfs.append(psf_val)
                    except ValueError:
                        continue
                        
        if cluster_psfs:
            cluster_psfs.sort()
            mid = len(cluster_psfs) // 2
            median_psf = (cluster_psfs[mid] + cluster_psfs[~mid]) / 2.0
            debug_log(f"[+] Local matches missing. Resolved {len(cluster_psfs)} regional matches on cluster '{cluster_key}'. Regional Median: ${median_psf:.2f} PSF.")
            return median_psf, f"{cluster_key} (CSV Extrapolated)", True
            
    except Exception as e:
        debug_log(f"[!] Error during regional CSV analysis step: {e}")

    # Absolute fallback
    cluster_region = CLUSTER_NAMES.get(cluster_key, "General Region")
    fallback_val = REGIONAL_FALLBACK_PSF.get(cluster_region, 16.0)
    return fallback_val, f"{cluster_region} (Pre-Set Baseline Fallback)", False

def fetch_json_safe(url, use_sg_proxy=False):
    """Safely fetches JSON using standard Python Requests with your native Proxy"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.hdb.gov.sg/"
    }
    
    # We only apply the proxy if requested (to save data)
    proxies = get_proxies() if use_sg_proxy else None
    
    try:
        res = requests.get(url, headers=headers, proxies=proxies, timeout=30)
        if res.status_code == 200:
            text = res.text
            if text.strip().startswith("<"): 
                debug_log("[!] FATAL: Firewall returned HTML instead of JSON API response!")
                return {}
            try:
                return json.loads(text)
            except Exception as e:
                debug_log(f"[!] Failed to parse JSON. Response preview: {text[:100]}")
                return {}
        else:
            debug_log(f"[!] Target URL returned HTTP {res.status_code}. Response preview: {res.text[:100]}")
    except Exception as e:
        debug_log(f"[!] Connection failed for {url}: {e}")
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
    if not target_lat or not target_lon: return 0
    return sum(1 for s in school_list if calculate_haversine_distance(target_lat, target_lon, s["lat"], s["lon"]) <= radius_meters)

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
        res = fetch_json_safe(url, use_sg_proxy=True) # Uses local proxy to fetch OneMap safely
        if res and res.get("found", 0) > 0:
            return float(res["results"][0]["LATITUDE"]), float(res["results"][0]["LONGITUDE"])
            
    # Hardcoded Structural Fallback for new BTO Towns like Tengah
    if "tengah" in address_string.lower() or (cluster_key and "tengah" in cluster_key.lower()):
        debug_log("[*] Known BTO Fallback Triggered: Tengah")
        return 1.3700, 103.7000 # Sector 69 Approximate Center
        
    return None, None

def format_display_address(raw_address):
    addr = raw_address.strip()
    addr = re.sub(r'([a-zA-Z])(\d+[\sA-Za-z])', r'\1, \2', addr)
    if ',' in addr:
        parts = [p.strip() for p in addr.split(',', 1)]
        if len(parts[0]) > 2 and len(parts[1]) > 2:
            return f"**{parts[0]}**\n📍 {parts[1]}"
    return f"**{addr}**"

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
    keys_to_check = ["currentBidClosingDate", "tenderClosingDate", "closingDate", "tenderEndDate", "endDate", "closeDate"]
    for k in keys_to_check:
        raw = deep_find(item, k)
        if raw:
            formatted = format_hdb_date(raw)
            if formatted != "TBA": return formatted

    if item_id:
        debug_log(f"[*] Date hidden in API. Hard-scraping frontend UI for unit {item_id}...")
        try:
            page_url = f"https://place2lease.hdb.gov.sg/public/view-properties/true/{link_path}/{item_id}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            proxies = get_proxies()
            
            html_res = requests.get(page_url, headers=headers, proxies=proxies, timeout=15)
            clean_text = clean_html(html_res.text)
            
            regex_pattern = r'(?:Tender closing on|Tender ends on|Closing Date|End Date)[\s:]*([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4}(?:[,\s]+[0-9]{1,2}:[0-9]{2}(?::[0-9]{2})?\s*(?:am|pm|AM|PM))?)'
            match = re.search(regex_pattern, clean_text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            
            generic_date_pattern = r'([0-9]{1,2}\s+[a-zA-Z]+\s+[0-9]{4}[,\s]+[0-9]{1,2}:[0-9]{2}\s*(?:am|pm|AM|PM))'
            generic_match = re.search(generic_date_pattern, clean_text, re.IGNORECASE)
            if generic_match:
                return generic_match.group(1).strip()
        except Exception as e:
            debug_log(f"[*] Fallback date scrape failed: {e}")
            
    return "TBA"

def scrape_hdb_place2lease():
    debug_log("[*] Intercepting internal HDB JSON feed...")
    listings = []
    page_num = 1
    max_pages = 10
    
    while page_num <= max_pages:
        # We use page_num and pageSize=50 to capture absolutely everything
        api_url = f"https://place2lease.hdb.gov.sg/webservice-public/api/v1/tender-units/public/search-tender-units?page={page_num}&pageSize=50&order=asc&orderProperty=lastPost.currentBidClosingDate&startIndex=0"
        
        # Passing use_sg_proxy=True uses your Ziny Proxy implicitly!
        payload = fetch_json_safe(api_url, use_sg_proxy=True)
        raw_units = []
        
        if not payload:
            debug_log(f"[!] Payload is empty on page {page_num}.")
            break

        if isinstance(payload, list): 
            raw_units = payload
        elif isinstance(payload, dict):
            total_elements = payload.get("totalElements")
            if total_elements == 0:
                debug_log("[*] HDB API confirms totalElements = 0.")
                break
                
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
            break

        debug_log(f"[+] Page {page_num}: Intercepted {len(raw_units)} raw properties. Filtering trades...")

        for item in raw_units:
            try:
                # 1. STRICT TRADE FILTERING (Tuition, Enrichment, Student Care, or Open)
                is_open = item.get("isOpenTrade", False)
                included_trades = item.get("includedTrades", []) or []
                
                target_trades = ["tuition", "enrichment", "student care"]
                trade_match = False
                
                if is_open:
                    trade_match = True
                    trade_type = "Open Trade"
                else:
                    matched_specific = [t for t in included_trades if any(kw in t.lower() for kw in target_trades)]
                    if matched_specific:
                        trade_match = True
                        trade_type = ", ".join(matched_specific)
                    else:
                        trade_type = ", ".join(included_trades) if included_trades else "Not Specified"
                
                if not trade_match:
                    continue # Skip hairdressers, generic retail, etc.
                    
                # 2. EXTRACT DATA
                item_id = str(item.get("tenderUnitId") or item.get("id", ""))
                full_address = item.get("address", "")
                
                # Fallback for address if empty
                if not full_address:
                    block = str(deep_find(item, "blockNo", "block") or "").strip()
                    street = str(deep_find(item, "streetName", "street") or "").strip()
                    unit_no = str(deep_find(item, "unitNo", "unit") or "").strip()
                    if block and street: full_address = f"Blk {block} {street}"
                    if unit_no and unit_no != "None": full_address += f" #{unit_no}"

                sqm = float(item.get("floorArea", 0) or 0)
                sqft = sqm * 10.7639
                if sqft < MIN_SQFT_LIMIT: continue

                matched_key = item.get("hdbTown", "Unmapped Region").title()
                
                price = float(item.get("currentBid") or item.get("highestBid") or item.get("tenderPrice") or item.get("price") or 0.0)
                tender_type = str(item.get("tenderType", "")).lower()
                is_sealed = ("price only" in tender_type or "sealed" in tender_type or price == 0.0)
                
                # End Date directly from JSON
                closing_date = item.get("bidClosingDate", "TBA")
                if closing_date != "TBA":
                    closing_date = closing_date.split(" ")[0] # Keep only "15-Jul-2026"
                
                # Media / Thumbnail
                image_url = ""
                medias = item.get("unitMedias", [])
                if medias and isinstance(medias, list) and len(medias) > 0:
                    image_url = medias[0].get("url", "")
                    if image_url.startswith("/"):
                        image_url = f"https://place2lease.hdb.gov.sg{image_url}"

                direct_link = f"https://place2lease.hdb.gov.sg/public/view-properties/true/ebid-unit-details/{item_id}" if item_id else "https://place2lease.hdb.gov.sg/public/"
                unique_id = f"HDB_{item_id}_{int(sqft)}"

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
                    "link": direct_link,
                    "image_url": image_url
                })
            except Exception as e:
                debug_log(f"[!] Processing error on item: {e}")
                
        # Pagination Check
        if isinstance(payload, dict):
            total_elements = payload.get("totalElements", 0)
            if page_num * 50 >= total_elements:
                break
        page_num += 1

    return listings

def load_price_ledger():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f: return json.load(f)
        except Exception: pass
    return {}

def save_price_ledger(ledger_dict):
    with open(STATE_FILE, "w") as f: json.dump(ledger_dict, f, indent=2)

def main():
    send_telegram_alert("🟢 **System Test:** Direct HDB API Pipeline live. Fetching active inventory...")
    
    # 1. ALWAYS download the latest commercial benchmark file directly from GitHub!
    fetch_latest_commercial_data()
    
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
        f"*{len(all_units)} Target Matches Currently Open for Bidding/Tender*"
    ]

    for unit in all_units:
        lid = unit["id"]
        current_price = unit["price"]
        
        if lid not in price_ledger: header_badge = "📍 **NEW HDB LEASE**"
        elif current_price > price_ledger.get(lid, 0.0) and current_price > 0 and not unit["is_sealed"]:
            header_badge = f"📈 **LIVE BID INCREASE** *(Was ${price_ledger[lid]:,.0f}/mth)*"
        else: header_badge = "📌 **ACTIVE HDB LEASE**"
            
        price_ledger[lid] = current_price

        # Dynamic Pricing Engine lookup using local sorted CSV
        est_private_psf, mapping_source, database_found = lookup_market_psf(unit["address"], unit["cluster_key"])
        
        # Derived formula applying the standard 35% HDB target discount on the source private price index
        hdb_psf_bid = est_private_psf * 0.65 
        est_monthly = hdb_psf_bid * unit['sqft']

        if unit["is_sealed"] or unit["price"] == 0:
            price_display = (
                f"💰 **🔒 Sealed Tender** (No upfront price listed)\n"
                f"💡 **Suggested Target Bid:** ~${est_monthly:,.0f} / mth (${hdb_psf_bid:.2f} PSF)\n"
                f"*(Derived via 35% HDB discount on ${est_private_psf:.2f} PSF Reference ({mapping_source}))*"
            )
        else:
            psf = round(unit["price"] / unit["sqft"], 2)
            psf_flag = " ⚠️ *(Above Market)*" if psf > MAX_PSF_THRESHOLD else ""
            price_display = (
                f"💰 **${unit['price']:,.0f} / mth** | **${psf:.2f} PSF**{psf_flag}\n"
                f"💡 **Suggested Target Bid:** ~${est_monthly:,.0f} / mth (${hdb_psf_bid:.2f} PSF)\n"
                f"*(Derived via 35% HDB discount on ${est_private_psf:.2f} PSF Reference ({mapping_source}))*"
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

        warning_block = "⚠️ **ACTION REQUIRED:** Verify no existing tuition/enrichment trades exist in this block."

        # Insert Image URL if available
        img_markdown = f"\n[🖼️ View Floorplan / Image]({unit['image_url']})" if unit.get('image_url') else ""

        block = (
            f"{header_badge}\n"
            f"🏢 {display_address}\n"
            f"🏷️ HDB Place2Lease ({unit['cluster_key'].title()})\n\n"
            f"📐 **{int(unit['sqft']):,} sqft** ({unit['sqm']} m²)\n"
            f"{price_display}\n\n"
            f"🛍️ **Trade Type:** {unit.get('trade_type', 'Not Specified')}\n"
            f"🗓️ **Tender Ends:** {unit.get('closing_date', 'TBA')}\n\n"
            f"📍 **Location & Local Catchment:**\n"
            f"• {schools_line}\n"
            f"• {buffer_line}\n\n"
            f"{warning_block}\n\n"
            f"🔗 [Find Out More]({unit['link']}){img_markdown}"
        ).strip()
        
        report_blocks.append(block)

    # Send the header
    header_text = "\n\n".join(report_blocks[:2])
    send_telegram_alert(header_text)
    time.sleep(1)

    # Send each property block individually
    for block in report_blocks[2:]:
        send_telegram_alert(block)
        time.sleep(1)

    save_price_ledger(price_ledger)
    debug_log("[+] Pipeline finished successfully.")

if __name__ == "__main__":
    main()
