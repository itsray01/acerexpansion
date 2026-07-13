import csv
import json
import time
import requests

# ==========================================
# 1. CONFIGURATION & CREDENTIALS
# ==========================================
ZENROWS_API_KEY = "0a72b44b388084523647e4dce2f6787701a1fbd6"
CSV_FILE_PATH = "Generalinformationofschools.csv"
OUTPUT_JSON_PATH = "school_db.json"

# Highly prestigious International/Private schools that aren't inside the MOE database
EXTRA_SCHOOLS = [
    {"name": "United World College of South East Asia (Dover)", "lat": 1.3039, "lon": 103.7801, "level": "INTERNATIONAL"},
    {"name": "United World College of South East Asia (East)", "lat": 1.3575, "lon": 103.9450, "level": "INTERNATIONAL"},
    {"name": "Overseas Family School", "lat": 1.3820, "lon": 103.9389, "level": "INTERNATIONAL"},
    {"name": "Singapore American School", "lat": 1.4310, "lon": 103.7788, "level": "INTERNATIONAL"},
    {"name": "Dulwich College (Singapore)", "lat": 1.3490, "lon": 103.7431, "level": "INTERNATIONAL"},
    {"name": "Tanglin Trust School", "lat": 1.2977, "lon": 103.7972, "level": "INTERNATIONAL"},
    {"name": "Australian International School", "lat": 1.3516, "lon": 103.8681, "level": "INTERNATIONAL"},
    {"name": "St. Joseph's Institution International", "lat": 1.3359, "lon": 103.8398, "level": "INTERNATIONAL"},
    {"name": "Stamford American International School", "lat": 1.3325, "lon": 103.8679, "level": "INTERNATIONAL"}
]

# ==========================================
# 2. RESOLUTION ENGINE (ONEMAP VIA ZENROWS)
# ==========================================
def resolve_gps(postal_code, school_name):
    """Pings OneMap API via ZenRows SG proxy to get highly accurate lat/lon coordinates."""
    zenrows_endpoint = "https://api.zenrows.com/v1/"
    
    # Attempt 1: Query by Postal Code (Most precise)
    queries = []
    if postal_code and str(postal_code).strip() != "na":
        queries.append(str(postal_code).strip())
    
    # Attempt 2: Query by School Name
    queries.append(f"{school_name} Singapore")
    
    for query in queries:
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={query}&returnGeom=Y&getAddrDetails=N&pageNum=1"
        params = {
            "url": url,
            "apikey": ZENROWS_API_KEY,
            "premium_proxy": "true",
            "proxy_country": "sg" # Defeat MOE/OneMap local firewalls
        }
        try:
            res = requests.get(zenrows_endpoint, params=params, timeout=15)
            if res.status_code == 200:
                data = res.json()
                if data.get("found", 0) > 0:
                    result = data["results"][0]
                    return float(result["LATITUDE"]), float(result["LONGITUDE"])
        except Exception as e:
            print(f"    [!] OneMap API warning for query '{query}': {e}")
        time.sleep(0.1) # Small rate limit delay to keep proxies clean
        
    return None, None

# ==========================================
# 3. DATABASE COMPILATION
# ==========================================
def build_db():
    print("[*] Launching offline Singapore School Database Builder...")
    compiled_schools = []
    
    # 1. Inject Manual International/Private Entries
    print(f"[*] Injecting {len(EXTRA_SCHOOLS)} baseline International and Private schools...")
    compiled_schools.extend(EXTRA_SCHOOLS)
    
    # 2. Load and Parse MOE CSV File
    print(f"[*] Loading raw records from '{CSV_FILE_PATH}'...")
    raw_rows = []
    try:
        with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_rows.append(row)
    except FileNotFoundError:
        print(f"[!] Critical Error: '{CSV_FILE_PATH}' not found in current folder.")
        print("[!] Please make sure the CSV is uploaded next to this script.")
        return

    # Filter out only legitimate MOE Academic schools
    academic_rows = []
    for row in raw_rows:
        level_code = str(row.get('mainlevel_code', '')).upper()
        # Strictly target primary, secondary, and junior college levels
        if any(keyword in level_code for keyword in ['PRIMARY', 'SECONDARY', 'JUNIOR COLLEGE', 'CENTRALIZED INSTITUTION', 'MIXED LEVELS']):
            academic_rows.append(row)
            
    total_schools = len(academic_rows)
    print(f"[+] Found {total_schools} MOE Academic schools. Starting automated GPS resolution...")
    
    resolved_count = 0
    failed_count = 0
    
    for index, row in enumerate(academic_rows, 1):
        name = row.get('school_name', 'Unknown School').strip()
        postal = row.get('postal_code', '').strip()
        level = row.get('mainlevel_code', 'ACADEMIC').strip().upper()
        
        print(f"[{index}/{total_schools}] Resolving {name} (Postal: {postal})...")
        
        lat, lon = resolve_gps(postal, name)
        
        if lat and lon:
            compiled_schools.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "level": level
            })
            resolved_count += 1
            print(f"    -> [SUCCESS] Coords: ({lat:.6f}, {lon:.6f})")
        else:
            failed_count += 1
            print(f"    -> [FAILED] Could not locate school. Dropping from database.")
            
    # 3. Save Compiled Database to JSON File
    print("\n===========================================")
    print("[*] Resolution complete.")
    print(f"[+] Successfully mapped: {resolved_count} schools.")
    if failed_count > 0:
        print(f"[!] Failed to map: {failed_count} schools (due to dead postal codes/names).")
    print(f"[*] Saving unified school database to '{OUTPUT_JSON_PATH}'...")
    
    with open(OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(compiled_schools, f, indent=2)
        
    print(f"✨ Success! '{OUTPUT_JSON_PATH}' compiled with {len(compiled_schools)} total educational institutions.")
    print("===========================================")

if __name__ == "__main__":
    build_db()
