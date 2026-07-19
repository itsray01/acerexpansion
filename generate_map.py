import json
import os
import requests
import csv
import math
import random
import folium
from folium import plugins
from folium import Element

# ==========================================
# 1. CONFIGURATION & PALETTE
# ==========================================
URA_GEOJSON_PATH = "ura_regions.json"
SCHOOL_DB_PATH = "All_Schools_Geocoded.csv"
MOE_DATA_PATH = "M850801_2.csv"
OUTPUT_MAP_PATH = "acer_expansion_map.html"

# Executive High-Contrast Corporate Palette
PALETTE = {
    "North": "#1E3A8A",   # Deep Royal Blue
    "West": "#059669",    # Emerald Green
    "East": "#D97706",    # Rich Amber
    "Central": "#DC2626"  # Crimson Red
}

# Anchors in the ocean for the Infographic Text Boxes
REGIONS_CONFIG = {
    "North": { "color": PALETTE["North"], "center": [1.415, 103.820], "anchor": [1.485, 103.820] },
    "West": { "color": PALETTE["West"], "center": [1.350, 103.700], "anchor": [1.350, 103.540] },
    "East": { "color": PALETTE["East"], "center": [1.355, 103.940], "anchor": [1.355, 104.080] },
    "Central": { "color": PALETTE["Central"], "center": [1.320, 103.825], "anchor": [1.230, 103.825] }
}

# Your Existing Branches
EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4325, 103.8408),
    "Admiralty Place (North)": (1.4404, 103.8003),
    "The Woodgrove (North)": (1.4311, 103.7844),
    "Vista Point (North)": (1.4315, 103.7937),
    "Canberra Plaza (North)": (1.4431, 103.8297),
    "Tampines West (East)": (1.3486, 103.9360),
    "Buangkok Square (East)": (1.3837, 103.8823),
    "Aljunied Maths/Science (East)": (1.3204, 103.8844),
    "Aljunied Languages (East)": (1.3206, 103.8846),
    "Elias Mall (East)": (1.3773, 103.9424),
    "Dawson (Central)": (1.2941, 103.8099),
    "Depot Heights (Central)": (1.2809, 103.8086),
    "Tiong Bahru (Central)": (1.2863, 103.8272),
    "Cantonment (Central)": (1.2766, 103.8413),
    "Commonwealth (Central)": (1.3025, 103.7983),
    "Senja Heights (West)": (1.3853, 103.7629),
    "Greenridge (West)": (1.3856, 103.7663),
    "Hong Kah (West)": (1.3496, 103.7210)
}

# ==========================================
# 2. SPATIAL & DATA PARSING ENGINES
# ==========================================
def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two GPS points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def load_schools_from_csv():
    """Smart CSV Loader: Resilient against empty fields and fuzzy column names."""
    schools = []
    if not os.path.exists(SCHOOL_DB_PATH):
        print(f"[!] Cannot find {SCHOOL_DB_PATH}.")
        return schools
        
    with open(SCHOOL_DB_PATH, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        h_map = {}
        
        # Fuzzy match headers
        for h in headers:
            h_lower = str(h).strip().lower()
            if 'name' in h_lower or 'school' in h_lower: h_map['name'] = h
            elif 'lat' in h_lower: h_map['lat'] = h
            elif 'lon' in h_lower or 'lng' in h_lower: h_map['lon'] = h
            elif 'level' in h_lower or 'type' in h_lower: h_map['level'] = h
            elif 'region' in h_lower: h_map['region'] = h
            elif 'address' in h_lower or 'addr' in h_lower: h_map['address'] = h
            elif 'tier' in h_lower: h_map['tier'] = h
            
        for row in reader:
            name = row.get(h_map.get('name', ''), '').strip()
            if not name: continue
            
            try:
                lat = float(row.get(h_map.get('lat', ''), '').strip())
                lon = float(row.get(h_map.get('lon', ''), '').strip())
            except ValueError:
                continue # Skip gracefully if GPS is completely missing
                
            level = row.get(h_map.get('level', ''), 'Unknown').strip()
            region = row.get(h_map.get('region', ''), 'Unknown').strip()
            address = row.get(h_map.get('address', ''), 'No Address').strip()
            tier = row.get(h_map.get('tier', ''), 'Standard').strip()
            
            schools.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "level": level,
                "region": region,
                "address": address,
                "tier": tier if tier else "Standard"
            })
            
    print(f"[*] Successfully loaded {len(schools)} schools from CSV.")
    return schools

def parse_moe_data():
    """Smart parser: extracts student counts without needing manual CSV cleanup."""
    student_data = {"North": "N/A", "West": "N/A", "East": "N/A", "Central": "N/A"}
    if not os.path.exists(MOE_DATA_PATH): return student_data
    try:
        temp_students = {"North": 0, "West": 0, "East": 0, "Central": 0}
        with open(MOE_DATA_PATH, 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row or len(row) < 2: continue
                col = row[0].strip()
                try: val = int(row[1].replace(',', '').strip())
                except: continue
                if "All Levels - Central" in col: temp_students["Central"] += val
                elif "All Levels - East" in col: temp_students["East"] += val
                elif "All Levels - North" in col and "North-East" not in col: temp_students["North"] += val
                elif "All Levels - North-East" in col: temp_students["North"] += val
                elif "All Levels - West" in col: temp_students["West"] += val
        if sum(temp_students.values()) > 0: student_data = temp_students
    except Exception as e:
        print(f"[!] Error parsing MOE data: {e}")
    return student_data

# ==========================================
# 3. MAP BUILDER
# ==========================================
def generate_map():
    print("[*] Booting up Master Infographic & Interactive Map Engine...")
    schools = load_schools_from_csv()
    if not schools: return
    student_data = parse_moe_data()
    
    # Initialize map with HARD BOUNDARY LOCKS
    m = folium.Map(
        location=[1.3521, 103.8198], 
        zoom_start=12, 
        min_zoom=12, 
        max_zoom=18,
        max_bounds=True,
        min_lat=1.15, max_lat=1.55,
        min_lon=103.50, max_lon=104.10,
        tiles=None
    )
    
    # Base Layers
    folium.TileLayer('OpenStreetMap', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='Executive Dark Canvas (Clean)', show=False).add_to(m)
    
    # Inject Custom CSS
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');
    .leaflet-tooltip {
        font-family: 'Montserrat', sans-serif !important; font-size: 15px !important; font-weight: 600 !important;
        padding: 10px 14px !important; background-color: rgba(20, 20, 20, 0.95) !important; color: white !important;
        border: 1px solid #888 !important; border-radius: 8px !important; box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    }
    
    /* OVERRIDE TO FORCE DARK POPUPS ON LEAFLET */
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {
        background-color: rgba(20, 20, 20, 0.95) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.6) !important;
    }
    .leaflet-popup-content { font-family: 'Montserrat', sans-serif !important; font-size: 14px !important; line-height: 1.4 !important; }
    
    .leaflet-control-layers { border: none !important; background: transparent !important; box-shadow: none !important; padding: 15px !important; margin-top: -15px !important; margin-right: -15px !important; }
    .leaflet-touch .leaflet-control-layers-toggle, .leaflet-retina .leaflet-control-layers-toggle, .leaflet-control-layers-toggle {
        margin-left: auto !important; background-image: url('https://i.imgur.com/YhyOq9V.png') !important; background-size: 65% !important;
        background-repeat: no-repeat !important; background-position: center !important; background-color: rgba(25, 25, 25, 0.85) !important;
        backdrop-filter: blur(10px) !important; -webkit-backdrop-filter: blur(10px) !important; border-radius: 14px !important;
        width: 55px !important; height: 55px !important; box-shadow: 0 6px 20px rgba(0,0,0,0.5) !important; border: 1px solid rgba(255,255,255,0.2) !important; transition: all 0.3s ease !important;
    }
    .leaflet-control-layers-toggle:hover { background-color: rgba(40, 40, 40, 0.95) !important; transform: scale(1.05) !important; border-color: #00E5FF !important; }
    .leaflet-control-layers-toggle span { display: none !important; }
    .leaflet-control-layers.leaflet-control-layers-expanded {
        margin-top: 5px !important; background: rgba(20, 20, 20, 0.85) !important; backdrop-filter: blur(16px) !important; -webkit-backdrop-filter: blur(16px) !important;
        color: #ffffff !important; border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 18px !important; padding: 22px 28px !important;
        font-family: 'Montserrat', sans-serif !important; box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important; min-width: 280px !important;
    }
    .leaflet-control-layers-list::before { content: "Map Display Settings"; display: block; font-size: 15px; font-weight: 700; color: #00E5FF; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 10px; }
    .leaflet-control-layers-list { font-size: 14px !important; margin-bottom: 0 !important; }
    .leaflet-control-layers-base label, .leaflet-control-layers-overlays label { display: flex !important; align-items: center !important; margin: 14px 0 !important; cursor: pointer !important; font-weight: 500 !important; transition: color 0.2s !important; }
    .leaflet-control-layers-base label:hover, .leaflet-control-layers-overlays label:hover { color: #FFD700 !important; }
    .leaflet-control-layers-separator { border-top: 1px solid rgba(255,255,255,0.15) !important; margin: 18px 0 !important; }
    input[type="checkbox"].leaflet-control-layers-selector, input[type="radio"].leaflet-control-layers-selector { appearance: none; -webkit-appearance: none; width: 18px !important; height: 18px !important; border: 2px solid #888 !important; border-radius: 4px; margin-right: 12px !important; cursor: pointer !important; position: relative; background: rgba(255,255,255,0.1); transition: all 0.2s; }
    input[type="radio"].leaflet-control-layers-selector { border-radius: 50%; }
    input[type="checkbox"].leaflet-control-layers-selector:checked, input[type="radio"].leaflet-control-layers-selector:checked { background: #00E5FF !important; border-color: #00E5FF !important; }
    input[type="checkbox"].leaflet-control-layers-selector:checked::after { content: "✔"; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #000; font-size: 12px; font-weight: bold; }
    input[type="radio"].leaflet-control-layers-selector:checked::after { content: ""; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 8px; height: 8px; background: #000; border-radius: 50%; }
    .region-label { position: relative !important; z-index: 9999 !important; font-family: 'Montserrat', sans-serif !important; font-size: 13px !important; text-transform: uppercase !important; letter-spacing: 3.5px !important; white-space: nowrap !important; pointer-events: none !important; transform: translate(-50%, -50%) !important; transition: all 0.2s ease !important; }
    
    #sidebar-backdrop { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.5); z-index: 99998; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
    #sidebar-backdrop.open { opacity: 1; pointer-events: auto; }
    #directory-btn { position: fixed; bottom: 30px; right: 20px; z-index: 9997; background-color: rgba(25, 25, 25, 0.85); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.2); color: white; padding: 12px 18px; border-radius: 8px; font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 14px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.5); transition: all 0.3s; display: flex; align-items: center; gap: 8px; }
    #directory-btn:hover { background-color: rgba(40,40,40,0.95); border-color: #00E5FF; color: #00E5FF; transform: translateY(-2px); }
    #side-panel { position: fixed; top: 0; right: -400px; width: 320px; height: 100vh; background-color: rgba(20, 20, 20, 0.90); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border-left: 1px solid rgba(255,255,255,0.1); z-index: 99999; transition: right 0.4s cubic-bezier(0.25, 0.8, 0.25, 1); color: white; font-family: 'Montserrat', sans-serif; display: flex; flex-direction: column; box-shadow: -5px 0 30px rgba(0,0,0,0.6); overflow: hidden; }
    #side-panel.open { right: 0; }
    .panel-header { display: flex; justify-content: space-between; align-items: center; padding: 20px 25px; border-bottom: 1px solid rgba(255,255,255,0.1); flex-shrink: 0; }
    .panel-header h2 { margin: 0; font-size: 16px; color: #00E5FF; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
    #close-panel { background: none; border: none; color: white; font-size: 28px; cursor: pointer; transition: color 0.2s; }
    #close-panel:hover { color: #FF3D00; }
    .panel-content { padding: 20px 25px; overflow-y: auto; flex-grow: 1; }
    .panel-content::-webkit-scrollbar { width: 6px; }
    .panel-content::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 4px; }
    .panel-content h3 { font-size: 15px; color: #FFD700; margin: 0 0 10px 0; padding-bottom: 8px; border-bottom: 1px dashed rgba(255,255,255,0.2); }
    .panel-content h4 { font-size: 13px; color: #38BDF8; margin: 20px 0 8px 0; text-transform: uppercase; letter-spacing: 1px; }
    .panel-content ul { list-style: none; padding: 0; margin: 0 0 20px 0; }
    .panel-content li { font-size: 12px; padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05); color: rgba(255,255,255,0.8); transition: color 0.2s; cursor: default; }
    .panel-content li:hover { color: white; background: rgba(255,255,255,0.05); padding-left: 5px; }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    # ==========================================
    # URA REGIONAL CHOROPLETH LAYER
    # ==========================================
    if os.path.exists(URA_GEOJSON_PATH):
        def style_function(feature):
            ura_region = feature['properties'].get('REGION_N', '')
            if ura_region == "WEST REGION": acer_region = "West"
            elif ura_region in ["NORTH REGION", "NORTH-EAST REGION"]: acer_region = "North"
            elif ura_region == "EAST REGION": acer_region = "East"
            elif ura_region == "CENTRAL REGION": acer_region = "Central"
            else: return {'fillOpacity': 0, 'weight': 0}
            color = PALETTE[acer_region]
            return { 'fillColor': color, 'color': color, 'weight': 1.5, 'fillOpacity': 0.35 }
        
        with open(URA_GEOJSON_PATH, 'r') as f:
            geo_data = json.load(f)
        folium.GeoJson(geo_data, name="Regional Boundaries (Choropleth)", style_function=style_function, show=False).add_to(m)

    # Calculate Metrics
    branch_counts = {"North": 0, "West": 0, "East": 0, "Central": 0}
    for name in EXISTING_BRANCHES.keys():
        for region in branch_counts.keys():
            if f"({region})"
