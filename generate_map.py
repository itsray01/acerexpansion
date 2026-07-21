import os
import csv
import json
import requests
import folium
from folium import plugins
from branca.element import Element

OUTPUT_MAP_PATH = "acer_expansion_map.html"

# Your 19 Active Branches with explicit regional tagging
EXISTING_BRANCHES = {
    # North (5)
    "Junction 9 (North)": (1.4325, 103.8408),
    "Admiralty Place (North)": (1.4404, 103.8003),
    "The Woodgrove (North)": (1.4311, 103.7844),
    "Vista Point (North)": (1.4315, 103.7937),
    "Canberra Plaza (North)": (1.4431, 103.8297),
    # East (4)
    "Tampines West (East)": (1.3486, 103.9360),
    "Aljunied Maths/Science (East)": (1.3204, 103.8844),
    "Aljunied Languages (East)": (1.3206, 103.8846),
    "Elias Mall (East)": (1.3773, 103.9424),
    # Central (5)
    "Dawson (Central)": (1.2941, 103.8099),
    "Depot Heights (Central)": (1.2809, 103.8086),
    "Tiong Bahru (Central)": (1.2863, 103.8272),
    "Cantonment (Central)": (1.2766, 103.8413),
    "Commonwealth (Central)": (1.3025, 103.7983),
    # West (5)
    "Senja Heights (West)": (1.3853, 103.7629),
    "Greenridge (West)": (1.3856, 103.7663),
    "Hong Kah (West)": (1.3496, 103.7210),
    "Dairy Farm (West)": (1.3655, 103.7744),
    "Beauty World (West)": (1.3425, 103.7765)
}

region_colors = {
    "NORTH": "#00E5FF",   # Sky Blue
    "EAST": "#FFFF00",    # Bright Yellow
    "WEST": "#4ADE80",    # Emerald Green
    "CENTRAL": "#F472B6"  # Rose Pink
}

# The 6 Largest Upcoming BTO Mega-Estates (2026 - 2030)
UPCOMING_BTOS = [
    {"name": "Tengah Mega-Estate", "lat": 1.3690, "lon": 103.7300, "yield": "30,000", "year": "2026-2028"},
    {"name": "Bayshore Precinct", "lat": 1.3142, "lon": 103.9400, "yield": "10,000", "year": "2027-2029"},
    {"name": "Mount Pleasant", "lat": 1.3283, "lon": 103.8340, "yield": "5,000", "year": "2027-2028"},
    {"name": "Ulu Pandan (Dover)", "lat": 1.3090, "lon": 103.7740, "yield": "3,000", "year": "2026-2027"},
    {"name": "Chencharu (Yishun)", "lat": 1.4080, "lon": 103.8200, "yield": "10,000", "year": "2027-2030"},
    {"name": "Woodlands North", "lat": 1.4450, "lon": 103.7900, "yield": "10,000", "year": "2028-2030"}
]

def load_competitors():
    """Loads the new competitor JSON database."""
    if os.path.exists("competitor_db.json"):
        with open("competitor_db.json", 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_schools():
    """Strictly loads GPS from school_db.json. Cross-references CSV for extra text data."""
    schools = []
    csv_metadata = {}
    
    csv_file = "Generalinformationofschools.csv" if os.path.exists("Generalinformationofschools.csv") else "All_Schools_Geocoded.csv"
    if os.path.exists(csv_file):
        print(f"[*] Harvesting metadata from {csv_file}...")
        with open(csv_file, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name_key = next((k for k in row.keys() if 'name' in str(k).lower() or 'school' in str(k).lower()), None)
                if not name_key: continue
                name = row[name_key].strip().lower()
                addr_key = next((k for k in row.keys() if 'address' in str(k).lower() and 'url' not in str(k).lower()), None)
                url_key = next((k for k in row.keys() if 'url' in str(k).lower() or 'website' in str(k).lower()), None)
                csv_metadata[name] = {
                    "address": row[addr_key] if addr_key and row[addr_key] else "Address not available",
                    "website": row[url_key] if url_key and row[url_key] else ""
                }

    json_data = None
    if os.path.exists("school_db.json"):
        print("[*] Loading exact GPS coordinates from local school_db.json...")
        with open("school_db.json", 'r', encoding='utf-8') as f:
            json_data = json.load(f)
    else:
        print("[!] Local school_db.json missing. Fetching from GitHub directly...")
        try:
            res = requests.get("https://raw.githubusercontent.com/itsray01/acerexpansion/main/school_db.json", timeout=10)
            if res.status_code == 200: json_data = res.json()
        except Exception as e:
            print(f"[!] Network fetch failed: {e}")

    if not json_data:
        print("[!] CRITICAL: Could not load school_db.json from anywhere. Map will lack schools.")
        return []

    for item in json_data:
        name = item.get("name", "").strip()
        lower_name = name.lower()
        if "lat" in item and "lon" in item:
            extra = csv_metadata.get(lower_name, {})
            website = extra.get("website", "")
            if website and not website.startswith("http"):
                website = "http://" + website
                
            schools.append({
                "name": name,
                "lat": float(item["lat"]),
                "lon": float(item["lon"]),
                "level": item.get("level", "PRIMARY"),
                "address": extra.get("address", "Address not available"),
                "website": website
            })
    
    print(f"[+] Successfully loaded {len(schools)} schools with strict pinpoint accuracy.")
    return schools

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    competitors = load_competitors()
    
    # SEAMLESS ZOOM: zoom_control=False removes +/- buttons. Micro-steps (0.2) ensure gentle scrolling.
    m = folium.Map(
        location=[1.3521, 103.8198],
        zoom_start=12,
        zoom_control=False,
        zoom_snap=0.1,
        zoom_delta=0.2,
        wheel_px_per_zoom_level=120,
        tiles=None
    )

    folium.TileLayer('CartoDB dark_matter', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    folium.TileLayer('OpenStreetMap', name='Standard Map', show=False).add_to(m)

    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    .leaflet-control-zoom { display: none !important; }

    /* PULSING ANIMATION FOR BTO ZONES */
    @keyframes pulse-white {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 15px rgba(255, 255, 255, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(255, 255, 255, 0); }
    }
    .bto-pulse {
        width: 14px; height: 14px; background-color: #FFFFFF;
        border-radius: 50%; border: 2px solid #000;
        animation: pulse-white 2s infinite;
    }
    
    /* PULSING ANIMATION FOR LIVE TENDERS */
    @keyframes pulse-green {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 15px rgba(16, 185, 129, 0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
    }
    .tender-pulse {
        width: 32px; height: 32px; background-color: #10B981;
        border-radius: 50%; border: 2px solid #FFFFFF;
        animation: pulse-green 2s infinite;
    }

    .competitor-pin {
        width: 10px; height: 10px; background-color: #555;
        border: 2px solid #FF3344; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }

    .leaflet-tooltip {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 13px !important; font-weight: 600 !important;
        padding: 6px 10px !important; background-color: rgba(20, 20, 20, 0.95) !important;
        color: white !important; border: 1px solid #888 !important; border-radius: 8px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    }
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {
        background: rgba(20, 20, 20, 0.95) !important;
        color: #fff !important; border: 1px solid rgba(255,255,255,0.15) !important;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5) !important; border-radius: 12px !important;
    }
    .leaflet-popup-content { font-family: 'Montserrat', sans-serif !important; margin: 15px !important; }

    .leaflet-control-layers {
        border: none !important; background: transparent !important; box-shadow: none !important;
        padding: 15px !important; margin-top: -15px !important; margin-right: -15px !important;
    }
    .leaflet-control-layers-toggle {
        margin-left: auto !important;
        background-image: url('https://i.imgur.com/YhyOq9V.png') !important;
        background-size: 65% !important; background-repeat: no-repeat !important; background-position: center !important;
        background-color: rgba(25, 25, 25, 0.85) !important;
        backdrop-filter: blur(10px) !important; border-radius: 14px !important;
        width: 55px !important; height: 55px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.5) !important;
        border: 1px solid rgba(255,255,255,0.2) !important; transition: all 0.3s ease !important;
    }
    .leaflet-control-layers-toggle:hover {
        background-color: rgba(40, 40, 40, 0.95) !important; transform: scale(1.05) !important; border-color: #00E5FF !important;
    }
    .leaflet-control-layers.leaflet-control-layers-expanded {
        margin-top: 5px !important; background: rgba(20, 20, 20, 0.90) !important;
        backdrop-filter: blur(16px) !important; color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 18px !important;
        padding: 20px 24px !important; font-family: 'Montserrat', sans-serif !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important; min-width: 250px !important;
    }
    .leaflet-control-layers-list::before {
        content: "Map Display Settings"; display: block; font-size: 14px; font-weight: 700; color: #00E5FF;
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 8px;
    }
    .leaflet-control-layers-base label, .leaflet-control-layers-overlays label {
        display: flex !important; align-items: center !important; margin: 12px 0 !important; cursor: pointer !important; font-weight: 500 !important; font-size: 13px !important; transition: color 0.2s !important;
    }
    .leaflet-control-layers-base label:hover, .leaflet-control-layers-overlays label:hover { color: #FFD700 !important; }
    .leaflet-control-layers-separator { border-top: 1px solid rgba(255,255,255,0.15) !important; margin: 14px 0 !important; }

    input[type="checkbox"].leaflet-control-layers-selector,
    input[type="radio"].leaflet-control-layers-selector {
        appearance: none; -webkit-appearance: none; width: 16px !important; height: 16px !important;
        border: 2px solid #888 !important; border-radius: 4px; margin-right: 10px !important; cursor: pointer !important;
        position: relative; background: rgba(255,255,255,0.1); transition: all 0.2s;
    }
    input[type="radio"].leaflet-control-layers-selector { border-radius: 50%; }
    input[type="checkbox"].leaflet-control-layers-selector:checked,
    input[type="radio"].leaflet-control-layers-selector:checked { background: #00E5FF !important; border-color: #00E5FF !important; }
    input[type="checkbox"].leaflet-control-layers-selector:checked::after {
        content: "✔"; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #000; font-size: 10px; font-weight: bold;
    }
    input[type="radio"].leaflet-control-layers-selector:checked::after {
        content: ""; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 6px; height: 6px; background: #000; border-radius: 50%;
    }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    print("[*] Plotting URA Regions (Bug Fixed: Strict Keyword Filtering)...")

    ura_group = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True)
    
    ura_data = None
    if os.path.exists("ura_regions.json"):
        with open("ura_regions.json", "r") as f:
            ura_data = json.load(f)
    else:
        try:
            res = requests.get("https://raw.githubusercontent.com/itsray01/acerexpansion/main/ura_regions.json", timeout=10)
            if res.status_code == 200: ura_data = res.json()
        except Exception as e:
            print(f"[!] URA network fetch failed: {e}")

    def get_vibrant_style(feature):
        props = str(feature.get('properties', {})).upper()
        # EXPLICITLY filter out Jurong East and Marina East from hitting the East catch
        if 'EAST' in props and 'NORTH-EAST' not in props and 'NORTHEAST' not in props and 'JURONG EAST' not in props and 'MARINA EAST' not in props:
            return {'fillColor': '#FFFF00', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.38, 'interactive': False}
        elif 'NORTH' in props or 'WOODLANDS' in props or 'SENGKANG' in props or 'PUNGGOL' in props or 'YISHUN' in props or 'ANG MO KIO' in props or 'HOUGANG' in props or 'SERANGOON' in props:
            return {'fillColor': '#00E5FF', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.22, 'interactive': False}
        elif 'WEST' in props or 'JURONG' in props or 'CLEMENTI' in props or 'BUKIT BATOK' in props or 'BUKIT PANJANG' in props or 'CHOA CHU KANG' in props:
            return {'fillColor': '#4ADE80', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.22, 'interactive': False}
        else:
            return {'fillColor': '#F472B6', 'color': 'transparent', 'weight': 0, 'fillOpacity': 0.22, 'interactive': False}

    if ura_data:
        folium.GeoJson(
            ura_data,
            style_function=get_vibrant_style
        ).add_to(ura_group)

    print("[*] Plotting Heatmap...")
    heatmap_group = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False)
    heat_data = [[s['lat'], s['lon']] for s in schools]
    plugins.HeatMap(
        heat_data, radius=38, blur=22, max_zoom=14, min_opacity=0.35,
        gradient={0.25: '#00E5FF', 0.5: '#4ADE80', 0.75: '#FFFF00', 1.0: '#FF3344'}
    ).add_to(heatmap_group)

    print(f"[*] Plotting {len(schools)} schools with organic student estimates...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True)
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True)
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True)
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True)
    
    stats = {"NORTH": [0,0,0], "EAST": [0,0,0], "WEST": [0,0,0], "CENTRAL": [0,0,0]}

    for school in schools:
        level = school.get("level", "").upper()
        lat, lon = school["lat"], school["lon"]
        name, address, website = school["name"], school["address"], school["website"]
        
        base_enrollment = 1350
        if "PRIMARY" in level: base_enrollment = 1280
        elif "SECONDARY" in level: base_enrollment = 1320
        elif "JUNIOR COLLEGE" in level: base_enrollment = 1850
        elif "INTERNATIONAL" in level: base_enrollment = 920
        
        variance = (sum(ord(c) for c in name) * 17) % 261 - 120
        school_students = base_enrollment + variance
        
        if (lon > 103.86 and lat > 1.36) or (lat > 1.375 and lon > 103.77):
            stats["NORTH"][1] += 1
            stats["NORTH"][2] += school_students
        elif lon > 103.89:
            stats["EAST"][1] += 1
            stats["EAST"][2] += school_students
        elif lon < 103.78 and lat < 1.38:
            stats["WEST"][1] += 1
            stats["WEST"][2] += school_students
        else:
            stats["CENTRAL"][1] += 1
            stats["CENTRAL"][2] += school_students
        
        if "PRIMARY" in level: fill_color, group = "#38BDF8", primary_group
        elif "SECONDARY" in level: fill_color, group = "#A78BFA", secondary_group
        elif "JUNIOR COLLEGE" in level: fill_color, group = "#FBBF24", jc_group
        elif "INTERNATIONAL" in level: fill_color, group = "#F472B6", intl_group
        else: continue
            
        safe_name = name.replace("'", "&#39;")
        btn_html = f"<a href='{website}' target='_blank' style='display: inline-block; background: #00E5FF; color: #000; padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 700; text-decoration: none; margin-top: 5px;'>View Website &rarr;</a>" if website else ""
        popup_html = f"""
        <div style="min-width: 200px;">
            <b style="color: {fill_color}; font-size: 15px;">{safe_name}</b><br>
            <div style="font-size: 11px; color: #aaa; text-transform: uppercase; margin-bottom: 8px; font-weight: 600;">{level.title()}</div>
            <div style="font-size: 12px; color: #fff; line-height: 1.4; margin-bottom: 8px;">&#128205; {address}</div>
            {btn_html}
        </div>
        """
            
        folium.CircleMarker(
            location=[lat, lon], radius=6, 
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=safe_name, color="white", weight=1, fill_color=fill_color, fill=True, fill_opacity=0.85
        ).add_to(group)

    print("[*] Plotting Competitors (Triangles)...")
    comp_group = folium.FeatureGroup(name="Competitor Network", show=False)
    for comp in competitors:
        brand = comp.get('brand', '')
        
        # Color mapping logic
        if brand == "Kumon":
            fill_color = "#0B132B" # Dark Dark Blue
        elif brand == "Mind Stretcher":
            fill_color = "#FAECA8" # Very Light Gold
        elif brand == "Zenith":
            fill_color = "#808080" # Gray
        elif brand == "Aspire Hub":
            fill_color = "#F97316" # Orange (Assigned for Aspire)
        elif brand == "The Learning Lab":
            fill_color = "#A28E5C" # Muted Gold
        else:
            fill_color = "#FFFFFF"

        # Sharp, scalable SVG Triangles
        svg_html = f'''
        <div style="transform: translate(-50%, -50%); filter: drop-shadow(0px 3px 4px rgba(0,0,0,0.8));">
            <svg width="22" height="20" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <polygon points="12,0 24,24 0,24" fill="{fill_color}" stroke="#FFFFFF" stroke-width="1.5" stroke-linejoin="round"/>
            </svg>
        </div>
        '''
        
        popup_html = f"<b style='color: {fill_color}; text-shadow: 1px 1px 2px #000;'>{brand}</b><br>{comp.get('branch', '')}"
        folium.Marker(
            location=[comp['lat'], comp['lon']],
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=f"{brand} ({comp.get('branch', '')})",
            icon=folium.DivIcon(html=svg_html, icon_anchor=(11, 10))
        ).add_to(comp_group)

    print("[*] Plotting Upcoming BTO Mega-Estates...")
    bto_group = folium.FeatureGroup(name="Upcoming BTO Estates (2026-2030)", show=False)
    for bto in UPCOMING_BTOS:
        popup_html = f"""
        <div style="min-width: 180px;">
            <b style="color: #FFF; font-size: 14px;">{bto['name']}</b><br>
            <div style="font-size: 11px; color: #00E5FF; text-transform: uppercase; margin-bottom: 6px; font-weight: 600;">Upcoming Mega-Estate</div>
            <div style="font-size: 12px; color: #ccc;"><b>Yield:</b> {bto['yield']} Units</div>
            <div style="font-size: 12px; color: #ccc;"><b>Completion:</b> {bto['year']}</div>
        </div>
        """
        folium.Marker(
            location=[bto['lat'], bto['lon']],
            popup=folium.Popup(popup_html, max_width=250),
            tooltip=bto['name'],
            icon=folium.DivIcon(html="<div class='bto-pulse'></div>", icon_anchor=(7, 7))
        ).add_to(bto_group)

    print("[*] Plotting Live HDB Tenders...")
    tenders_group = folium.FeatureGroup(name="Live HDB Tenders (Actionable)", show=True)
    
    live_tenders = []
    if os.path.exists("live_tenders.json"):
        try:
            with open("live_tenders.json", "r", encoding="utf-8") as f:
                live_tenders = json.load(f)
        except Exception as e:
            print(f"Error reading local live_tenders.json: {e}")
    else:
        try:
            res = requests.get("https://raw.githubusercontent.com/itsray01/acerexpansion/main/live_tenders.json", timeout=10)
            if res.status_code == 200: 
                live_tenders = res.json()
        except:
            pass

    if live_tenders:
        for tender in live_tenders:
            try:
                lat = tender.get("lat")
                lon = tender.get("lon")
                if not lat or not lon: continue
                
                # Robust extraction for old vs new JSON structures
                address = tender.get('address', '')
                project = tender.get('project', 'Unknown')
                if project == 'Unknown' or not project:
                    # Smart extraction: Grabs the street name instead of the block number
                    parts = [p.strip() for p in address.split(',')]
                    if len(parts) > 1:
                        project = parts[1] # e.g. "Upper Cross Street"
                    else:
                        project = address.split(',')[0] if address else 'Commercial Unit'
                        
                raw_price = tender.get('price', 'TBA')
                size_sqft = tender.get('size_sqft', tender.get('sqft', 'N/A'))
                psf = tender.get('psf', 'N/A')
                
                # If PSF is missing but we have price and sqft, do the math!
                if psf == 'N/A' and raw_price != 'TBA' and size_sqft != 'N/A':
                    try:
                        clean_price = float(str(raw_price).replace('$', '').replace('/mo', '').replace(',', ''))
                        clean_sqft = float(size_sqft)
                        if clean_sqft > 0:
                            psf = round(clean_price / clean_sqft, 2)
                    except:
                        pass
                        
                psf_display = f"${psf:.2f}" if isinstance(psf, (int, float)) else (f"${psf}" if psf != 'N/A' else "TBA")
                size_display = f"{size_sqft} sqft" if size_sqft != 'N/A' else "N/A sqft"
                link_url = tender.get('url', tender.get('link', 'https://place2lease.hdb.gov.sg/'))
                
                popup_html = f"""
                <div style="font-family: 'Montserrat', sans-serif; width: 220px;">
                    <h4 style="margin: 0 0 5px 0; color: #10B981; font-weight: 800;">🟢 LIVE TENDER</h4>
                    <b style="font-size: 14px;">{project}</b><br>
                    <span style="color: #ccc; font-size: 12px;">{address}</span>
                    <hr style="margin: 8px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.2);">
                    <b>Rent:</b> {raw_price}<br>
                    <b>Size:</b> {size_display}<br>
                    <b>PSF:</b> {psf_display}<br>
                    <hr style="margin: 8px 0; border: 0; border-top: 1px solid rgba(255,255,255,0.2);">
                    <a href="{link_url}" target="_blank" style="display: inline-block; background: #10B981; color: #000; padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 800; text-decoration: none; margin-top: 5px;">Bid on Portal &rarr;</a>
                </div>
                """
                
                # Custom Storefront SVG Icon
                store_svg = '''<svg viewBox="0 0 24 24" stroke-linecap="round" stroke-linejoin="round" style="width:16px; height:16px; stroke:#FFF; fill:none; stroke-width:2;"><path d="M2 7h20"/><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><path d="M15 22v-4a2 2 0 0 0-2-2h-2a2 2 0 0 0-2 2v4"/><path d="m2 7 4.41-4.41A2 2 0 0 1 7.83 2h8.34a2 2 0 0 1 1.42.59L22 7"/></svg>'''
                
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip="🟢 Live HDB Tender",
                    icon=folium.DivIcon(html=f"<div class='tender-pulse' style='display:flex; align-items:center; justify-content:center;'>{store_svg}</div>", icon_anchor=(16, 16))
                ).add_to(tenders_group)
            except Exception as e:
                print(f"Error mapping tender: {e}")

    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Branches...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        if "(North)" in name or "North" in name: stats["NORTH"][0] += 1
        elif "(East)" in name or "East" in name: stats["EAST"][0] += 1
        elif "(West)" in name or "West" in name: stats["WEST"][0] += 1
        else: stats["CENTRAL"][0] += 1
        
        icon_html = """
        <div style="background-color: transparent; border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border: 2px solid #ffffff; box-shadow: 0 4px 10px rgba(0,0,0,0.5); overflow: hidden;">
            <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; height: 100%; object-fit: contain;">
        </div>
        """
        
        safe_branch_name = name.replace("'", "&#39;")
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{safe_branch_name}",
            tooltip=f"★ {safe_branch_name}",
            icon=folium.DivIcon(html=icon_html, icon_size=(32, 32), icon_anchor=(16, 16))
        ).add_to(branch_group)
        
        folium.Circle(
            location=[lat, lon], radius=1500, color="#00C9FF", weight=2, fill_color="#00C9FF", fill_opacity=0.18
        ).add_to(branch_group)

    sim_group = folium.FeatureGroup(name="Simulate Expansion (Click Map)", show=False)

    print("[*] Plotting Regional Data Boxes...")
    boxes_group = folium.FeatureGroup(name="Regional Data Boxes", show=True)
    
    def create_box(region, b_count, s_count, total_students):
        r_color = region_colors.get(region, "#FFFFFF")
        return """
        <div style="background: rgba(15,15,15,0.95); padding: 14px; border-radius: 8px; border: 1px solid """ + r_color + """55; color: white; font-family: 'Montserrat', sans-serif; width: 160px; box-shadow: 0 8px 20px rgba(0,0,0,0.6); backdrop-filter: blur(8px);">
            <div style="font-size: 13px; font-weight: 800; margin-bottom: 10px; color: """ + r_color + """;">■ """ + region + """</div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Branches:</span><b style="color: #FBBF24;">""" + str(b_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Schools:</span><b style="color: #38BDF8;">""" + str(s_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #aaa;"><span>Students:</span><b style="color: #4ADE80;">""" + f"{total_students:,}" + """</b></div>
        </div>
        """

    regions_setup = [
        ("NORTH", [1.485, 103.82]),
        ("EAST",  [1.35, 104.02]),
        ("WEST",  [1.364, 103.64]),
        ("CENTRAL",[1.225, 103.82])
    ]

    # Cleaned up UI: No dashed lines pointing into the map
    for reg_name, box_coord in regions_setup:
        folium.Marker(
            location=box_coord,
            icon=folium.DivIcon(html=create_box(reg_name, stats[reg_name][0], stats[reg_name][1], stats[reg_name][2]), icon_size=(160, 100), icon_anchor=(80, 50))
        ).add_to(boxes_group)

    legend_and_sim_js = """
    <div id="map-legend" style="
        position: fixed; top: 20px; left: 20px; z-index: 9999;
        background: rgba(15, 15, 15, 0.90); backdrop-filter: blur(10px);
        padding: 14px 18px; border-radius: 10px; border: 1px solid rgba(255,255,255,0.15);
        font-family: 'Montserrat', sans-serif; font-size: 13px; color: #fff;
        box-shadow: 0 8px 20px rgba(0,0,0,0.6); pointer-events: auto;
        max-height: 85vh; overflow-y: auto;
    ">
        <div style="font-weight: 800; font-size: 13px; color: #00E5FF; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 6px;">Map Legend</div>
        
        <div style="display: flex; align-items: center; margin-bottom: 6px;"><span style="display:inline-block; width:10px; height:10px; background:#38BDF8; border-radius:50%; margin-right:10px;"></span> Primary School</div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;"><span style="display:inline-block; width:10px; height:10px; background:#A78BFA; border-radius:50%; margin-right:10px;"></span> Secondary School</div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;"><span style="display:inline-block; width:10px; height:10px; background:#FBBF24; border-radius:50%; margin-right:10px;"></span> Junior College</div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;"><span style="display:inline-block; width:10px; height:10px; background:#F472B6; border-radius:50%; margin-right:10px;"></span> International School</div>
        
        <div style="font-weight: 800; font-size: 11px; color: #FF3344; text-transform: uppercase; letter-spacing: 1px; margin-top: 10px; margin-bottom: 6px; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 8px;">Competitor Network</div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" style="margin-right:10px; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.8));"><polygon points="12,0 24,24 0,24" fill="#0B132B" stroke="#FFF" stroke-width="2"/></svg> Kumon
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" style="margin-right:10px; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.8));"><polygon points="12,0 24,24 0,24" fill="#FAECA8" stroke="#FFF" stroke-width="2"/></svg> Mind Stretcher
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" style="margin-right:10px; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.8));"><polygon points="12,0 24,24 0,24" fill="#808080" stroke="#FFF" stroke-width="2"/></svg> Zenith
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 4px;">
            <svg width="12" height="12" viewBox="0 0 24 24" style="margin-right:10px; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.8));"><polygon points="12,0 24,24 0,24" fill="#F97316" stroke="#FFF" stroke-width="2"/></svg> Aspire Hub
        </div>
        <div style="display: flex; align-items: center; margin-bottom: 6px;">
            <svg width="12" height="12" viewBox="0 0 24 24" style="margin-right:10px; filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.8));"><polygon points="12,0 24,24 0,24" fill="#A28E5C" stroke="#FFF" stroke-width="2"/></svg> The Learning Lab
        </div>

        <div style="display: flex; align-items: center; margin-top: 8px; border-top: 1px solid rgba(255,255,255,0.15); padding-top: 8px;">
            <span style="display:inline-block; width:12px; height:12px; border:2px solid #00C9FF; border-radius:50%; margin-right:10px;"></span> 1.5km Branch Catchment
        </div>
        <div style="display: flex; align-items: center; margin-top: 6px;">
            <span style="display:inline-block; width:12px; height:12px; background:#10B981; border:2px solid #FFF; border-radius:50%; margin-right:10px; box-shadow: 0 0 8px #10B981;"></span> <b style="color: #10B981;">Live HDB Tender</b>
        </div>
        <div style="display: flex; align-items: center; margin-top: 6px;">
            <span style="display:inline-block; width:12px; height:12px; border:2px dashed #FFFF00; background:rgba(255,255,0,0.2); border-radius:50%; margin-right:10px;"></span> Simulated Catchment
        </div>
        <div style="display: flex; align-items: center; margin-top: 6px;">
            <span style="display:inline-block; width:12px; height:12px; background:#FFF; border-radius:50%; margin-right:10px; box-shadow: 0 0 6px #FFF;"></span> Upcoming BTO Estate
        </div>
    </div>
    
    <script>
    window.addEventListener('load', function() {
        setTimeout(function() {
            // Menu Separator Injection
            var overlays = document.querySelector('.leaflet-control-layers-overlays');
            if (overlays) {
                var labels = overlays.querySelectorAll('label');
                labels.forEach(function(lbl) {
                    var txt = lbl.textContent;
                    if (txt.includes('Acer Academy Branches')) {
                        lbl.insertAdjacentHTML('beforebegin', '<div style="color:#00E5FF; font-size:11px; font-weight:800; margin-top:5px; margin-bottom:5px; text-transform:uppercase; letter-spacing:1px;">Core Strategy</div>');
                    }
                    if (txt.includes('Primary Schools')) {
                        lbl.insertAdjacentHTML('beforebegin', '<div style="color:#00E5FF; font-size:11px; font-weight:800; margin-top:15px; margin-bottom:5px; text-transform:uppercase; letter-spacing:1px;">Education Network</div>');
                    }
                    if (txt.includes('Regional Boundaries')) {
                        lbl.insertAdjacentHTML('beforebegin', '<div style="color:#00E5FF; font-size:11px; font-weight:800; margin-top:15px; margin-bottom:5px; text-transform:uppercase; letter-spacing:1px;">Analytics & Geography</div>');
                    }
                });
            }

            for (var key in window) {
                if (key.startsWith('map_')) {
                    var map = window[key];
                    var simLayer = L.layerGroup().addTo(map);
                    
                    map.on('click', function(e) {
                        var labels = document.querySelectorAll('.leaflet-control-layers-overlays label');
                        var simActive = false;
                        labels.forEach(function(lbl) {
                            if (lbl.textContent.includes('Simulate Expansion') && lbl.querySelector('input').checked) {
                                simActive = true;
                            }
                        });
                        
                        if (simActive) {
                            simLayer.clearLayers();
                            L.circle(e.latlng, {
                                radius: 1500, color: '#FFFF00', weight: 3, dashArray: '6, 6', fillColor: '#FFFF00', fillOpacity: 0.25
                            }).addTo(simLayer);
                            
                            L.marker(e.latlng, {
                                icon: L.divIcon({
                                    className: 'sim-pin',
                                    html: '<div style="background:#FFFF00; color:#000; font-family:Montserrat; font-size:10px; font-weight:800; padding:4px 8px; border-radius:12px; border:2px solid #000; white-space:nowrap; box-shadow:0 3px 8px rgba(0,0,0,0.6); transform: translate(-50%, -150%);">★ NEW SIMULATED BRANCH</div>',
                                    iconSize: [0, 0]
                                })
                            }).addTo(simLayer);
                        }
                    });
                }
            }
        }, 1000);
    });
    </script>
    """
    m.get_root().html.add_child(Element(legend_and_sim_js))

    # --- ENDER DRAGON HEATMAP BAR ---
    ender_dragon_js = """
    <div id="heatmap-health-bar" style="
        display: none;
        position: fixed; top: 20px; left: 50%; transform: translateX(-50%); z-index: 9999;
        background: rgba(15, 15, 15, 0.90); backdrop-filter: blur(10px);
        padding: 12px 24px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.15);
        font-family: 'Montserrat', sans-serif; color: #fff; text-align: center;
        box-shadow: 0 10px 30px rgba(0,0,0,0.8); pointer-events: none;
    ">
        <div style="font-weight: 800; font-size: 13px; color: #fff; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 10px; text-shadow: 0 2px 4px rgba(0,0,0,0.8);">
            Student Density Heatmap
        </div>
        <div style="width: 350px; height: 14px; border-radius: 7px; background: linear-gradient(to right, #00E5FF, #4ADE80, #FFFF00, #FF3344); margin-bottom: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.6); border: 1px solid rgba(255,255,255,0.2);"></div>
        <div style="display: flex; justify-content: space-between; font-size: 11px; color: #ccc; font-weight: 700; text-transform: uppercase;">
            <span>Cold (Low)</span>
            <span>Hot (High)</span>
        </div>
    </div>
    <script>
    window.addEventListener('load', function() {
        setTimeout(function() {
            var bar = document.getElementById('heatmap-health-bar');
            for (var key in window) {
                if (key.startsWith('map_')) {
                    var map = window[key];
                    // Listen for when layers are turned on or off
                    map.on('overlayadd', function(e) {
                        if (e.name.includes('Heatmap')) bar.style.display = 'block';
                    });
                    map.on('overlayremove', function(e) {
                        if (e.name.includes('Heatmap')) bar.style.display = 'none';
                    });
                }
            }
        }, 1000);
    });
    </script>
    """
    m.get_root().html.add_child(Element(ender_dragon_js))

    # The order added here dictates the order they appear in the top right menu
    branch_group.add_to(m)
    tenders_group.add_to(m)
    comp_group.add_to(m)
    bto_group.add_to(m)
    
    primary_group.add_to(m)
    secondary_group.add_to(m)
    jc_group.add_to(m)
    intl_group.add_to(m)
    
    ura_group.add_to(m)
    heatmap_group.add_to(m)
    boxes_group.add_to(m)
    sim_group.add_to(m)

    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
