import os
import re
import json
import math
import time
import csv
import requests
import pandas as pd
from playwright.sync_api import sync_playwright

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

def send_telegram_alert(markdown_message, image_url=None):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        debug_log("[!] Telegram credentials missing from environment.")
        return
        
    try:
        if image_url:
            # Use sendPhoto to natively attach the image to the chat bubble
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, 
                "photo": image_url,
                "caption": markdown_message, 
                "parse_mode": "Markdown"
            }
            res = requests.post(url, json=payload, timeout=10)
            
            # If the image upload fails, gracefully fall back to text
            if res.status_code != 200:
                debug_log(f"[*] Native Photo Upload Failed ({res.status_code}). Falling back to text-mode...")
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                fallback_msg = f"{markdown_message}\n\n[🖼️ View Floorplan]({image_url})"
                payload = {
                    "chat_id": TELEGRAM_CHAT_ID,
                    "text": fallback_msg,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": False
                }
                requests.post(url, json=payload, timeout=10)
        else:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID, 
                "text": markdown_message, 
                "parse_mode": "Markdown", 
                "disable_web_page_preview": True
            }
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
    if not os.path.exists(MARKET_DATA_FILE):
        debug_log(f"[*] Reference file {MARKET_DATA_FILE} not found. Reverting to regional baseline.")
        cluster_region = CLUSTER_NAMES.get(cluster_key, "General Region")
        return REGIONAL_FALLBACK_PSF.get(cluster_region, 16.0), "Baseline Fallback", False

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
            debug_log(f"[+] Found {len(matching_psfs)} direct market matches. Localized Median: ${median_psf:.2f} PSF.")
            return median_psf, "Direct Match", True

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
            debug_log(f"[+] Regional matches resolved on cluster '{cluster_key}'. Regional Median: ${median_psf:.2f} PSF.")
            return median_psf, f"CSV: {cluster_key}", True
            
    except Exception as e:
        debug_log(f"[!] Error during regional CSV analysis step: {e}")

    # Absolute fallback
    cluster_region = CLUSTER_NAMES.get(cluster_key, "General Region")
    fallback_val = REGIONAL_FALLBACK_PSF.get(cluster_region, 16.0)
    return fallback_val, "Baseline Fallback", False

def fetch_json_safe(url, use_sg_proxy=False):
    """Safely fetches JSON using standard Python Requests with your native Proxy"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.hdb.gov.sg/"
    }
    
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
        res = fetch_json_safe(url, use_sg_proxy=True) 
        if res and res.get("found", 0) > 0:
            return float(res["results"][0]["LATITUDE"]), float(res["results"][0]["LONGITUDE"])
            
    if "tengah" in address_string.lower() or (cluster_key and "tengah" in cluster_key.lower()):
        debug_log("[*] Known BTO Fallback Triggered: Tengah")
        return 1.3700, 103.7000 
        
    return None, None

def format_display_address(raw_address):
    return raw_address.strip()

def extract_starting_bid(item_id):
    """
    Spins up Playwright exclusively for E-Bidding units to render Angular
    and extract the hidden starting bid from the DOM.
    """
    if not item_id:
        return 0.0

    url = f"https://place2lease.hdb.gov.sg/public/view-properties/true/ebid-unit-details/{item_id}"
    debug_log(f"[*] E-Bidding unit detected. Booting Playwright to scrape Starting Bid DOM for ID: {item_id}...")

    try:
        with sync_playwright() as p:
            proxy_settings = None
            if PROXY_HOST and PROXY_PORT:
                proxy_settings = {
                    "server": f"http://{PROXY_HOST}:{PROXY_PORT}",
                    "username": PROXY_USER,
                    "password": PROXY_PASS
                }

            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                proxy=proxy_settings,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            
            # Navigate and wait for Angular to load the network requests
            page.goto(url, wait_until="networkidle", timeout=45000)
            
            # Wait specifically for the price class to be injected into the DOM
            page.wait_for_selector(".text-start.bold", timeout=15000)
            
            # Grab all matching classes (just in case there are multiple)
            elements = page.query_selector_all(".text-start.bold")
            for el in elements:
                text = el.inner_text().strip()
                # Ensure it's a monetary value (e.g., "$7,500.00", "7500")
                if "$" in text or text.replace(",", "").replace(".", "").isdigit():
                    # Extract the pure number
                    match = re.search(r'([0-9]{1,3}(?:,[0-9]{3})*(?:\.\d{2})?)', text)
                    if match:
                        clean_val = match.group(1).replace(',', '')
                        bid_value = float(clean_val)
                        if bid_value > 500: # Sanity check (HDB rents are > $500)
                            browser.close()
                            debug_log(f"    -> Successfully extracted Playwright DOM Bid: ${bid_value}")
                            return bid_value

            browser.close()
    except Exception as e:
        debug_log(f"[!] Playwright scrape failed for {item_id}: {e}")

    return 0.0

def scrape_hdb_place2lease():
    debug_log("[*] Intercepting internal HDB JSON feed...")
    listings = []
    page_num = 1
    max_pages = 10
    
    while page_num <= max_pages:
        api_url = f"https://place2lease.hdb.gov.sg/webservice-public/api/v1/tender-units/public/search-tender-units?page={page_num}&pageSize=50&order=asc&orderProperty=lastPost.currentBidClosingDate&startIndex=0"
        
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
                # 1. STRICT TRADE FILTERING
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
                    continue 
                    
                # 2. EXTRACT DATA
                item_id = str(item.get("tenderUnitId") or item.get("id", ""))
                full_address = item.get("address", "")
                
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
                
                # Fetch Current/Highest Price
                price = float(item.get("currentBid") or item.get("highestBid") or item.get("tenderPrice") or item.get("price") or 0.0)
                
                # Fetch Tender Type exactly as written in the main API
                tender_type_raw = str(item.get("tenderType", "Unknown"))
                tender_type = tender_type_raw.lower()
                
                is_sealed = ("price only" in tender_type or "sealed" in tender_type)
                
                # === PLAYWRIGHT INTEGRATION ===
                starting_bid = 0.0
                if "e-bidding" in tender_type:
                    starting_bid = extract_starting_bid(item_id)
                
                # End Date directly from JSON
                closing_date = item.get("bidClosingDate", "TBA")
                if closing_date != "TBA":
                    closing_date = closing_date.split(" ")[0]
                
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
                    "starting_bid": starting_bid,
                    "is_sealed": is_sealed,
                    "tender_type_raw": tender_type_raw,
                    "tender_type": tender_type,
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
    send_telegram_alert("🟢 *System Test:* Direct HDB API Pipeline live. Fetching active inventory...")
    
    # 1. ALWAYS download the latest commercial benchmark file directly from GitHub
    fetch_latest_commercial_data()
    
    price_ledger = load_price_ledger()
    school_list = load_school_db()
    all_units = scrape_hdb_place2lease()
    
    debug_log(f"[*] Found {len(all_units)} qualified active HDB properties.")
    
    if not all_units:
        log_text = "\n".join(DEBUG_LOGS[-15:])
        error_msg = f"ℹ️ *HDB Feed Diagnostic:* 0 properties matched criteria.\n\n*Auto-Debug Logs:*\n```text\n{log_text}\n```"
        send_telegram_alert(error_msg)
        return

    # Container to hold all processed alerts
    property_alerts = []

    for unit in all_units:
        lid = unit["id"]
        current_price = unit["price"]
        
        if lid not in price_ledger: 
            header_badge = "🆕 *NEW TENDER*"
        elif current_price > price_ledger.get(lid, 0.0) and current_price > 0 and not unit["is_sealed"]:
            header_badge = f"📈 *BID INCREASED* (Was ${price_ledger[lid]:,.0f}/mo)"
        else: 
            header_badge = "📌 *ACTIVE TENDER*"
            
        price_ledger[lid] = current_price

        # Dynamic Pricing Engine lookup using local sorted CSV
        est_private_psf, mapping_source, database_found = lookup_market_psf(unit["address"], unit["cluster_key"])
        
        hdb_psf_bid = est_private_psf * 0.65 
        est_monthly = hdb_psf_bid * unit['sqft']

        # Determine Display Price & Status
        tender_type_display = unit.get("tender_type_raw", "Unknown").title()
        
        if unit["is_sealed"]:
            price_status = "🔒 Sealed Tender"
        else:
            display_price = unit["price"] if unit["price"] > 0 else unit.get("starting_bid", 0)
            psf = round(display_price / unit["sqft"], 2) if unit["sqft"] > 0 else 0.0
            psf_flag = " ⚠️ (Above Market)" if psf > MAX_PSF_THRESHOLD else ""
            
            # Format display based on whether E-Bidding Starting Bid exists
            if "e-bidding" in unit["tender_type"] and unit.get("starting_bid", 0) > 0:
                if unit["price"] > 0 and unit["price"] > unit["starting_bid"]:
                    price_status = f"${unit['price']:,.0f}/mo (Starts at ${unit['starting_bid']:,.0f}) (${psf:.2f} psf){psf_flag}"
                else:
                    price_status = f"${unit['starting_bid']:,.0f}/mo (Starting Bid) (${psf:.2f} psf){psf_flag}"
            elif display_price > 0:
                price_status = f"${display_price:,.0f}/mo (${psf:.2f} psf){psf_flag}"
            else:
                price_status = "TBA (Check Listing for Price)"

        lat, lon = get_robust_gps(unit["address"], cluster_key=unit["cluster_key"])
        display_address = format_display_address(unit['address'])

        # Catchment analysis strings
        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            schools_count = count_local_schools(lat, lon, school_list)
            
            schools_line = f"Schools <1.5km: {schools_count}" 
            buffer_line = f"Nearest Branch: {round(dist/1000, 1)}km ({nearest_branch})"
            if dist < 800: buffer_line += " ⚠️ *(Too Close)*"
        else:
            schools_line = "Schools <1.5km: *GPS Missing*"
            buffer_line = "Nearest Branch: *GPS Missing*"

        # Smart Warning Check
        trade_type_str = unit.get('trade_type', 'Not Specified')
        target_trades = ["tuition", "enrichment", "student care", "open trade"]
        
        if any(kw in trade_type_str.lower() for kw in target_trades):
            warning_block = ""
        else:
            warning_block = "⚠️ _Action Required: Verify no existing tuition/enrichment trades exist in this block._\n\n"

        # Ultra-Clean Modern UI Format
        block = (
            f"{header_badge} | *{unit['cluster_key'].title()}*\n"
            f"🏢 *{display_address}*\n\n"
            f"📐 *Size:* {int(unit['sqft']):,} sqft ({unit['sqm']} m²)\n"
            f"📋 *Allowed Trades:* {trade_type_str}\n"
            f"🏷️ *Tender Type:* {tender_type_display}\n"
            f"⏳ *Closing Date:* {unit.get('closing_date', 'TBA')}\n\n"
            f"💵 *Valuation & Bidding:*\n"
            f"• Current Ask: {price_status}\n"
            f"• Market Rate: ${est_private_psf:.2f} psf ({mapping_source})\n"
            f"• 🎯 *Target Bid:* *${hdb_psf_bid:.2f} psf* (~${est_monthly:,.0f}/mo)\n\n"
            f"📍 *Catchment Analysis:*\n"
            f"• {schools_line}\n"
            f"• {buffer_line}\n\n"
            f"{warning_block}"
            f"[🔗 View Listing on HDB Place2Lease]({unit['link']})"
        ).strip()
        
        property_alerts.append({
            "text": block,
            "image_url": unit.get("image_url")
        })

    # Send Introduction Message
    header_text = f"🏢 *ACER ACADEMY: ACTIVE HDB INVENTORY* 🏢\n_{len(all_units)} Target Matches Currently Open for Bidding/Tender_"
    send_telegram_alert(header_text)
    time.sleep(1)

    # Send each property block with embedded photos individually
    for alert in property_alerts:
        send_telegram_alert(alert["text"], alert["image_url"])
        time.sleep(1.5) # Slight delay to prevent Telegram rate-limiting

    save_price_ledger(price_ledger)
    debug_log("[+] Pipeline finished successfully.")

if __name__ == "__main__":
    main()
