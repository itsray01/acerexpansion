import os
import re
import json
import math
import time
import requests
from playwright.sync_api import sync_playwright

# ==========================================
# 1. CONFIGURATION & TARGET METRICS
# ==========================================


# Maximum floor area in square meters (~1,200 sqft)
MAX_AREA_SQM = 111.5 
MAX_PSF_THRESHOLD = 15.0  # Alert threshold for high rents

# Target HDB Towns (West, Central, East/NE Clusters)
TARGET_TOWNS = [
    # West Cluster
    "JURONG WEST", "JURONG EAST", "CLEMENTI", "BUKIT BATOK", 
    "CHOA CHU KANG", "BUKIT PANJANG", "BOON LAY",
    # Central Cluster
    "TOA PAYOH", "BISHAN", "KALLANG/WHAMPOA", "QUEENSTOWN", 
    "BUKIT MERAH", "CENTRAL AREA",
    # East & NE Cluster
    "SERANGOON", "HOUGANG", "SENGKANG", "PUNGGOL", 
    "TAMPINES", "BEDOK", "PASIR RIS", "GEYLANG"
]

# Trade types suitable for tuition/enrichment
VALID_TRADES_REGEX = re.compile(r"(open trade|education|tuition|enrichment|school|shop for specific trade|retail)", re.IGNORECASE)

# Coordinates of existing Acer Academy branches (Lat, Lon) for cannibalization checks
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
    """Calculates distance in meters between two GPS coordinates without external libraries."""
    R = 6371000  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def check_cannibalization(target_lat, target_lon):
    """Returns nearest Acer branch name and distance in meters."""
    nearest_branch = None
    min_dist = float('inf')
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        dist = calculate_haversine_distance(target_lat, target_lon, lat, lon)
        if dist < min_dist:
            min_dist = dist
            nearest_branch = name
    return nearest_branch, min_dist

def get_onemap_data(address):
    """Geocodes address via OneMap API and returns lat, lon, and postal code."""
    try:
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={address}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
        res = requests.get(url, timeout=10).json()
        if res.get("found", 0) > 0:
            result = res["results"][0]
            return float(result["LATITUDE"]), float(result["LONGITUDE"]), result.get("POSTAL", "")
    except Exception as e:
        print(f"[!] OneMap geocoding failed for {address}: {e}")
    return None, None, None

def count_nearby_primary_schools(lat, lon):
    """Queries OneMap for primary schools within a 1.5km radius."""
    try:
        # Free OneMap public theme service for primary schools
        url = f"https://www.onemap.gov.sg/api/public/themesvc/retrieveTheme?queryName=primaryschool"
        res = requests.get(url, timeout=10).json()
        count = 0
        if "SrchResults" in res:
            for school in res["SrchResults"][1:]: # Index 0 is metadata
                s_lat, s_lon = float(school["LATITUDE"]), float(school["LONGITUDE"])
                if calculate_haversine_distance(lat, lon, s_lat, s_lon) <= 1500:
                    count += 1
        return count
    except Exception as e:
        print(f"[!] School lookup failed: {e}")
        return 0

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

# ==========================================
# 3. PLAYWRIGHT SCRAPER LOGIC
# ==========================================
def scrape_place2lease():
    listings = []
    print("[*] Launching Playwright browser...")
    
    with sync_playwright() as p:
        # Launch headless Chromium
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Navigate to Place2Lease public listing page
        url = "https://place2lease.hdb.gov.sg/public/"
        print(f"[*] Navigating to {url}...")
        page.goto(url, wait_until="networkidle")
        time.sleep(3) # Allow JavaScript rendering to stabilize
        
        # Extract property cards/rows
        # Note: Selectors target standard HDB card components; Playwright text extraction handles structure variations
        cards = page.locator(".card, .property-item, tr").all()
        print(f"[*] Found {len(cards)} raw elements on page.")
        
        for card in cards:
            try:
                text = card.inner_text()
                
                # Basic validation that this element contains real property data
                if "sqm" not in text.lower() or "s(" not in text.lower():
                    continue
                
                # Extract Town
                town_match = None
                for t in TARGET_TOWNS:
                    if t in text.upper():
                        town_match = t
                        break
                if not town_match:
                    continue # Ignore units outside West, Central, and East/NE clusters
                
                # Extract Size in SQM
                sqm_match = re.search(r"([\d\.]+)\s*sqm", text, re.IGNORECASE)
                if not sqm_match:
                    continue
                size_sqm = float(sqm_match.group(1))
                if size_sqm > MAX_AREA_SQM:
                    continue # Ignore units > 1,200 sqft
                
                # Extract Trade Type
                if not VALID_TRADES_REGEX.search(text):
                    continue # Ignore restricted trades like F&B or clinic only
                
                # Extract Address using Singapore postal code regex: S(XXXXXX)
                addr_match = re.search(r"([^\n]+S\(\d{6}\))", text)
                address = addr_match.group(1).strip() if addr_match else f"HDB Commercial Unit ({town_match})"
                
                # Extract Current Bid / Rent
                bid_match = re.search(r"\$\s*([\d,]+\.?\d*)", text)
                current_bid = float(bid_match.group(1).replace(",", "")) if bid_match else 0.0
                
                # Generate unique listing ID based on address
                listing_id = re.sub(r"[^a-zA-Z0-9]", "", address)
                
                listings.append({
                    "id": listing_id,
                    "town": town_match,
                    "address": address,
                    "sqm": size_sqm,
                    "sqft": round(size_sqm * 10.7639, 1),
                    "bid": current_bid,
                    "raw_text": text
                })
            except Exception as e:
                continue
                
        browser.close()
        print(f"[*] Scraped {len(listings)} qualified listings after filtering.")
        return listings

# ==========================================
# 4. ORCHESTRATION & REPORTING
# ==========================================
def main():
    seen_listings = load_seen_listings()
    new_units = scrape_place2lease()
    
    # Filter out previously sent listings
    unseen_units = [u for u in new_units if u["id"] not in seen_listings]
    print(f"[*] Found {len(unseen_units)} brand new units to report.")
    
    if not unseen_units:
        print("[*] No new units to report. Exiting cleanly.")
        return

    report_blocks = [
        "🚨 **ACER ACADEMY: BI-WEEKLY EXPANSION INTEL** 🚨",
        f"*Scraped from HDB Place2Lease • {len(unseen_units)} New Qualified Units Found*",
        "---"
    ]
    
    for idx, unit in enumerate(unseen_units, 1):
        # Calculate PSF
        psf = round(unit["bid"] / unit["sqft"], 2) if unit["bid"] > 0 else 0.0
        psf_display = f"${psf} PSF" if psf > 0 else "No Bids Yet"
        psf_flag = " ⚠️ *(Above Average)*" if psf > MAX_PSF_THRESHOLD else " *(Reasonable)*"
        
        # Enrich via OneMap
        lat, lon, postal = get_onemap_data(unit["address"])
        
        # Calculate intelligence metrics
        if lat and lon:
            nearest_branch, dist = check_cannibalization(lat, lon)
            schools_count = count_nearby_primary_schools(lat, lon)
            
            # Formulate strategic tag
            if dist < 800:
                tag = "⚠️ **[HIGH CANNIBALIZATION RISK]**"
                verdict = f"Only **{int(dist)}m** from {nearest_branch}! Relocation candidate only."
            elif schools_count >= 3 and dist > 2000:
                tag = "🌟 **[PRIME EXPANSION GAP]**"
                verdict = f"Excellent catchment (**{schools_count} primary schools** within 1.5km) & **{round(dist/1000, 1)}km** away from {nearest_branch}."
            else:
                tag = "📍 **[VIABLE LOCATION]**"
                verdict = f"**{schools_count} primary schools** within 1.5km. Nearest center: {nearest_branch} ({round(dist/1000, 1)}km)."
        else:
            tag = "📍 **[NEW LISTING]**"
            verdict = "GPS geocoding unavailable. Manual distance check required."
            
        block = (
            f"{tag}\n"
            f"**{idx}. {unit['address']}**\n"
            f"• **Town / Cluster:** {unit['town']}\n"
            f"• **Size:** {unit['sqm']} sqm ({unit['sqft']} sqft)\n"
            f"• **Current Rent:** ${unit['bid']:,.2f}/mth | **{psf_display}**{psf_flag if psf > 0 else ''}\n"
            f"• **AI Strategic Verdict:** {verdict}\n"
            f"🔗 [View on HDB Place2Lease](https://place2lease.hdb.gov.sg/public/)\n"
            f"🔗 [Search on Google Maps](https://www.google.com/maps/search/?api=1&query={re.sub(r' ', '+', unit['address'])})"
        )
        report_blocks.append(block)
        report_blocks.append("---")
        
        # Add to state tracking
        seen_listings.add(unit["id"])
        time.sleep(1) # Polite API pacing
        
    # Send compiled report to Telegram Channel
    full_message = "\n\n".join(report_blocks)
    
    # Telegram has a 4096 character limit per message; chunk if necessary
    if len(full_message) <= 4096:
        send_telegram_alert(full_message)
    else:
        for i in range(0, len(report_blocks), 5):
            chunk = "\n\n".join(report_blocks[i:i+5])
            send_telegram_alert(chunk)
            time.sleep(1)
            
    # Save updated seen state
    save_seen_listings(seen_listings)
    print("[+] State updated. Pipeline execution complete!")

if __name__ == "__main__":
    main()
