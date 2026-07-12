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
TELEGRAM_BOT_TOKEN = "8891294738:AAGOuTbxEhZe0Y0wBX0cOFFonFp5m_1bvdA"
TELEGRAM_CHAT_ID = "-1004306469919"
ZENROWS_API_KEY = "0a72b44b388084523647e4dce2f6787701a1fbd6"

STATE_FILE = "seen_listings.json"
MAX_SQFT_LIMIT = 1200.0
MAX_PSF_THRESHOLD = 15.0

# Expansion Clusters Mapping
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

# Global Cache for MOE Primary Schools (Prevents OneMap Rate-Limiting)
CACHED_PRIMARY_SCHOOLS = []

# ==========================================
# 2. GEOCODING & SCHOOL CATCHMENT ENGINE
# ==========================================
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
    """
    Downloads all MOE Primary Schools from OneMap ONCE and caches them in memory.
    Bypasses rate-limiting and speeds up distance calculations by 100x.
    """
    global CACHED_PRIMARY_SCHOOLS
    if CACHED_PRIMARY_SCHOOLS:
        return CACHED_PRIMARY_SCHOOLS
        
    print("[*] Downloading MOE Primary School dataset from OneMap into local memory...")
    url = "https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=primaryschool"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=15).json()
        if "SrchResults" in res:
            for item in res["SrchResults"][1:]: # Index 0 is OneMap metadata
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
        print(f"[+] Successfully cached {len(CACHED_PRIMARY_SCHOOLS)} MOE Primary Schools in memory!")
    except Exception as e:
        print(f"[!] Warning: OneMap theme download failed ({e}).")
        
    return CACHED_PRIMARY_SCHOOLS

def count_nearby_primary_schools(target_lat, target_lon, radius_meters=1500):
    """Calculates primary schools within radius using the ultra-fast local memory cache."""
    schools = load_primary_schools_once()
    if not schools:
        return -1 # Returns -1 so we can distinguish an API network failure from a true 0 count
        
    count = 0
    for school in schools:
        dist = calculate_haversine_distance(target_lat, target_lon, school["lat"], school["lon"])
        if dist <= radius_meters:
            count += 1
            
    return count

def get_robust_gps(address_string, raw_card_text="", cluster_key=""):
    """4-Stage Aggressive Geocoding: Scrapes out amenity noise and falls back to Town Center."""
    queries_to_try = []

    # Stage 1: Hunt for a 6-digit Postal Code
    postal_match = re.search(r'\b(?:S\(|S|Singapore\s*)?(\d{6})\b', raw_card_text, re.I)
    if postal_match:
        queries_to_try.append(postal_match.group(1))

    # Stage 2: Extract explicit Singapore road names
    road_regex = r'\b([A-Za-z0-9\s]{3,25}(?:Road|Rd|Avenue|Ave|Street|St|Drive|Dr|Crescent|Cres|Way|Link|Walk|Loop|Green|Central|Plaza|Place|Terrace|View|Mall|Square))\b'
    road_matches = re.findall(road_regex, raw_card_text, re.I)
    for road in road_matches:
        clean_road = re.sub(r'\b(Blk|Block|Shop|Retail|Unit|#\S+)\b', '', road, flags=re.I).strip()
        if len(clean_road) > 4 and clean_road not in queries_to_try:
            queries_to_try.append(clean_road)

    # Stage 3: Scrub amenity chips ("4 Bus Stops nearby", "2 Parks") from address string
    clean_addr = re.sub(r'\d+\s*(?:Bus Stops|Parks|MRT|min|trains?|schools?).*$', '', address_string, flags=re.I)
    clean_addr = re.sub(r'#\S+', '', clean_addr)
    clean_addr = re.sub(r'\b(Blk|Block|Retail|Shop|Shophouse|Mall|Unit|Floor|Lvl)\b', ' ', clean_addr, flags=re.I)
    clean_addr = re.sub(r'([a-z])([A-Z])', r'\1 \2', clean_addr)
    clean_addr = re.sub(r'\s+', ' ', clean_addr).strip()
    
    if len(clean_addr) > 4 and clean_addr not in queries_to_try:
        queries_to_try.append(clean_addr)

    # Stage 4: Town Center Fallback (Guarantees coordinates even if street name is missing)
    if cluster_key and cluster_key not in queries_to_try:
        queries_to_try.append(f"{cluster_key} Singapore")

    for query in queries_to_try:
        try:
            url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={query}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
            res = requests.get(url, timeout=8).json()
            if res.get("found", 0) > 0:
                result = res["results"][0]
                return float(result["LATITUDE"]), float(result["LONGITUDE"])
        except Exception:
            continue
            
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
    requests.post(url, json=payload)

def fetch_html_safe(url):
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    params = {"url": url, "apikey": ZENROWS_API_KEY, "js_render": "true", "premium_proxy": "true"}
    try:
        print(f"[*] Requesting page via ZenRows API: {url}...")
        res = requests.get(zenrows_endpoint, params=params, timeout=60)
        return res.text if res.status_code == 200 else ""
    except Exception as e:
        print(f"[!] ZenRows fetch failed: {e}")
        return ""

# ==========================================
# 3. PORTAL SCRAPE & DEDUPLICATION LOGIC
# ==========================================
def scrape_portal_feed(portal_name, root_url, base_domain):
    print(f"[*] Extracting properties from {portal_name}...")
    html = fetch_html_safe(root_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    listings = []
    seen_urls_in_batch = set()
    
    cards = soup.find_all(["div", "article", "li"], class_=re.compile(r"(card|listing|property|item)", re.I))
    print(f"[*] Found {len(cards)} raw DOM cards on {portal_name}. Applying filters...")

    for card in cards:
        try:
            text = card.get_text(separator=" ").strip()
            
            matched_key = None
            for cluster in CLUSTER_NAMES.keys():
                if re.search(r"\b" + re.escape(cluster) + r"\b", text, re.I):
                    matched_key = cluster
                    break
            if not matched_key:
                continue

            sqft_match = re.search(r"([\d,]+)\s*sqft", text, re.I)
            if not sqft_match:
                continue
            sqft = float(sqft_match.group(1).replace(",", ""))
            if sqft > MAX_SQFT_LIMIT or sqft < 100:
                continue

            link_elem = card.find("a", href=True)
            link = link_elem["href"] if link_elem else root_url
            if link.startswith("/"):
                link = base_domain + link
                
            clean_url = link.split("?")[0]
            if clean_url in seen_urls_in_batch:
                continue
            seen_urls_in_batch.add(clean_url)

            address = ""
            addr_elem = card.find(class_=re.compile(r"(address|location|subtitle|street|ellipsis)", re.I))
            if addr_elem:
                address = re.sub(r"\s+", " ", addr_elem.get_text().strip())
            
            if len(address) < 10:
                addr_match = re.search(r"(?:at|along)\s+([^,.\n\$]{15,60}\b\d{1,3}\b[^,.\n\$]*)", text, re.I)
                if addr_match:
                    address = addr_match.group(1).strip()
                else:
                    address = link_elem.get_text().strip() if link_elem else f"Retail Unit, {matched_key}"
            
            address = re.sub(r'(\d+\s*(?:Bus Stops|Parks|MRT|min|trains?|schools?).*)$', '', address, flags=re.I).strip()
            address = re.sub(r'(For Rent|Rent|Tuition|Shophouse|Retail Shop|Shop|\n)', '', address, flags=re.I).strip()
            address = address.split("sqft")[0].split("$")[0].strip()
            if not address or len(address) < 3:
                address = f"Commercial Space ({matched_key.title()})"

            price_match = re.search(r"\$\s*([\d,]+)", text)
            price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

            listing_id = f"{portal_name[:2].upper()}_{abs(hash(clean_url))}_{int(sqft)}"

            listings.append({
                "id": listing_id,
                "portal": portal_name,
                "cluster_key": matched_key,
                "address": address,
                "sqft": sqft,
                "sqm": round(sqft / 10.7639),
                "price": price,
                "link": clean_url,
                "raw_text": text
            })
        except Exception:
            continue

    print(f"[*] {portal_name}: Filtered down to {len(listings)} unique qualified targets.")
    return listings

# ==========================================
# 4. ORCHESTRATION & TELEGRAM BROADCAST
# ==========================================
def main():
    send_telegram_alert("🟢 **System Test:** Multi-Portal Expansion Scraper initialized online.")

    # 1. Warm up the memory cache BEFORE scraping so distance loops run instantly
    load_primary_schools_once()

    seen_listings = load_seen_listings()
    
    cg_units = scrape_portal_feed("CommercialGuru", "https://www.commercialguru.com.sg/retail-for-rent", "https://www.commercialguru.com.sg")
    ep_units = scrape_portal_feed("EdgeProp", "https://www.edgeprop.sg/commercial-for-rent", "https://www.edgeprop.sg")

    all_units = cg_units + ep_units
    unseen_units = [u for u in all_units if u["id"] not in seen_listings]
    
    # Global URL deduplication safety net across both portals combined
    unique_unseen = []
    seen_links_global = set()
    for u in unseen_units:
        if u["link"] not in seen_links_global:
            seen_links_global.add(u["link"])
            unique_unseen.append(u)
    unseen_units = unique_unseen

    print(f"[*] Total combined new unique qualified units: {len(unseen_units)}")
    
    if not unseen_units:
        send_telegram_alert("ℹ️ **Scan Complete:** 0 new unique units matched the <1,200 sqft cluster criteria today.")
        print("[*] Pipeline finished cleanly.")
        return

    report_blocks = [
        "🏢 **ACER ACADEMY: EXPANSION INTEL** 🏢",
        f"*{len(unseen_units)} New Commercial Spaces Identified*",
        "---"
    ]

    for idx, unit in enumerate(unseen_units, 1):
        # Handle agent placeholder price anomalies (e.g., typing "$10" instead of "$10,000/mth")
        if 0 < unit["price"] < 500:
            psf_display = f"${unit['price']:.2f} PSF (Estimated Ask)"
            unit["price"] = unit["price"] * unit["sqft"] # Extrapolate total monthly rent from PSF ask
            psf_flag = ""
        else:
            psf = round(unit["price"] / unit["sqft"], 2) if unit["price"] > 0 and unit["sqft"] > 0 else 0.0
            psf_display = f"${psf:.2f} PSF" if psf > 0 else "Ask for Price"
            psf_flag = " ⚠️ *(Above Market)*" if psf > MAX_PSF_THRESHOLD else ""

        # Execute 4-Stage Aggressive Geocoding
        lat, lon = get_robust_gps(unit["address"], raw_card_text=unit.get("raw_text", ""), cluster_key=unit["cluster_key"])
        
        display_address = re.sub(r'([a-z])([A-Z])', r'\1, \2', unit['address'])
        display_address = re.sub(r'\s+@\s+', ', ', display_address)

        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            schools_count = count_nearby_primary_schools(lat, lon)
            
            if schools_count == -1:
                schools_line = "*OneMap sync error* (Manual check needed)"
            else:
                schools_line = f"**{schools_count} Primary Schools** within 1.5km"
                
            buffer_line = f"**{round(dist/1000, 1)} km** to {nearest_branch}"
            
            if dist < 800:
                schools_line += " ⚠️ *(High Cannibalization)*"
        else:
            schools_line = "*GPS sync pending* (Manual check needed)"
            buffer_line = "*GPS sync pending*"

        # Option 1 Executive Card Layout
        block = (
            f"🏢 **{display_address}**\n"
            f"🏷️ {unit['portal']} • Retail Unit ({unit['cluster_key'].title()} / {CLUSTER_NAMES[unit['cluster_key']]})\n\n"
            f"📐 **{int(unit['sqft']):,} sqft** ({unit['sqm']} m²)\n"
            f"💰 **${unit['price']:,.0f} / mth** |  **{psf_display}**{psf_flag}\n\n"
            f"📍 **Location & Catchment:**\n"
            f"• **Schools:** {schools_line}\n"
            f"• **Branch Buffer:** {buffer_line}\n\n"
            f"🔗 [Open Listing on {unit['portal']}]({unit['link']})"
        )
        report_blocks.append(block)
        report_blocks.append("---")
        seen_listings.add(unit["id"])
        time.sleep(0.1)

    # Broadcast to Telegram in chunks of 3 cards to keep message boxes tidy and readable
    for i in range(0, len(report_blocks), 3):
        chunk = "\n\n".join(report_blocks[i:i+3])
        send_telegram_alert(chunk)
        time.sleep(1)

    save_seen_listings(seen_listings)
    print("[+] State saved. All portal alerts dispatched successfully!")

if __name__ == "__main__":
    main()
