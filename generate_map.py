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
            if 'url' in h_lower or 'website' in h_lower or 'link' in h_lower: h_map['url'] = h
            elif 'name' in h_lower or 'school' in h_lower: h_map['name'] = h
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
            url = row.get(h_map.get('url', ''), '').strip()
            tier = row.get(h_map.get('tier', ''), 'Standard').strip()
            
            schools.append({
                "name": name,
                "lat": lat,
                "lon": lon,
                "level": level,
                "region": region,
                "address": address,
                "url": url,
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
            if f"({region})" in name: branch_counts[region] += 1

    school_counts = {"North": 0, "West": 0, "East": 0, "Central": 0}
    for s in schools:
        s_region = s.get('region', '')
        if "West" in s_region: school_counts["West"] += 1
        elif "East" in s_region: school_counts["East"] += 1
        elif "North" in s_region: school_counts["North"] += 1
        elif "Central" in s_region: school_counts["Central"] += 1
        else:
            # Fallback mathematical grouping
            lat, lon = s.get('lat', 0), s.get('lon', 0)
            if lon < 103.75: school_counts["West"] += 1
            elif lon > 103.88: school_counts["East"] += 1
            elif lat > 1.37: school_counts["North"] += 1
            else: school_counts["Central"] += 1

    # ==========================================
    # SPATIAL ANALYSIS: SCHOOLS & EXPANSION
    # ==========================================
    potential_expansion_coords = []
    schools_dir = {"PRIMARY": [], "SECONDARY": [], "JUNIOR COLLEGE": [], "INTERNATIONAL": []}

    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)")
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)")
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)")
    
    for school in schools:
        level = school.get("level", "").upper()
        lat, lon = school["lat"], school["lon"]
        name, address, tier = school["name"], school["address"], school["tier"]
        url = school.get("url", "")
        
        # The pure GPS is used for the heatmap to guarantee density aggregates perfectly
        is_covered = any(haversine(lat, lon, b_lat, b_lon) <= 1500 for b_lat, b_lon in EXISTING_BRANCHES.values())
        if not is_covered:
            potential_expansion_coords.append([lat, lon])
        
        if "PRIMARY" in level: fill_color, group, cat = "#38BDF8", primary_group, "PRIMARY"
        elif "SECONDARY" in level: fill_color, group, cat = "#A78BFA", secondary_group, "SECONDARY"
        elif "JUNIOR COLLEGE" in level: fill_color, group, cat = "#FBBF24", jc_group, "JUNIOR COLLEGE"
        elif "INTERNATIONAL" in level: fill_color, group, cat = "#F472B6", intl_group, "INTERNATIONAL"
        else: continue
        
        schools_dir[cat].append(name)
        
        # Add micro-scatter so grouped neighborhood schools fan out instead of perfectly overlapping
        vis_lat = lat + random.uniform(-0.0025, 0.0025)
        vis_lon = lon + random.uniform(-0.0025, 0.0025)
        
        url_html = f'<br><b style="color: #FFFFFF;">🌐 Web:</b> <a href="{url}" target="_blank" style="color: #38BDF8; text-decoration: none; font-weight: 600;">Visit Website ↗</a>' if url and str(url).startswith('http') else ''
        
        # Premium Executive HTML Popup Card
        popup_html = f"""
        <div style="font-family: 'Montserrat', sans-serif; min-width: 220px; padding: 4px;">
            <div style="font-size: 14px; font-weight: 800; color: {fill_color}; margin-bottom: 6px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px;">
                {name}
            </div>
            <div style="display: inline-block; background: rgba(255, 215, 0, 0.1); border: 1px solid #FFD700; color: #FFD700; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-bottom: 10px;">
                ★ TIER: {tier.upper()}
            </div>
            <div style="font-size: 11px; color: #CCCCCC; line-height: 1.5;">
                <b style="color: #FFFFFF;">Level:</b> {level.title()}<br>
                <b style="color: #FFFFFF;">Region:</b> {school.get('region', 'N/A').title()}<br>
                <b style="color: #FFFFFF;">📍 Addr:</b> {address}{url_html}
            </div>
        </div>
        """
        
        folium.CircleMarker(
            location=[vis_lat, vis_lon], radius=7, popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"<span style='font-size: 14px;'>{name}</span>", color="white", weight=1, fill_color=fill_color, fill=True, fill_opacity=0.85, class_name="school-dot"
        ).add_to(group)
        
    for grp in [primary_group, secondary_group, jc_group, intl_group]: grp.add_to(m)

    # Heatmap & Simulation Layers
    heatmap_group = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False)
    if potential_expansion_coords:
        plugins.HeatMap(potential_expansion_coords, name="Potential Expansion Zones", radius=25, blur=20, gradient={0.4: '#00C9FF', 0.65: '#A78BFA', 1.0: '#F472B6'}).add_to(heatmap_group)
    heatmap_group.add_to(m)

    sim_group = folium.FeatureGroup(name="Simulate New Branch (Click Map)", show=False)
    sim_group.add_to(m)

    # Plot Acer Academy Branches & Rings
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        gradient_style = "background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); border-radius: 50%; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; color: white; font-size: 14px; box-shadow: 0 0 12px rgba(0,0,0,0.5); border: 2px solid white; overflow: hidden;"
        icon_html = f'<div style="{gradient_style}"><img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; object-fit: contain;"></div>'
        
        folium.Marker(location=[lat, lon], popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{name}", tooltip=f"<span style='font-size: 16px; font-weight: bold; white-space: nowrap;'>★ {name}</span>", icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))).add_to(branch_group)
        folium.Circle(location=[lat, lon], radius=1500, popup=f"1.5km Ring: {name}", color="#00C9FF", weight=2, fill_color="#00C9FF", fill_opacity=0.18).add_to(branch_group)
    branch_group.add_to(m)

    # ==========================================
    # INFOGRAPHIC OCEAN BOXES & LEADER LINES
    # ==========================================
    infographic_group = folium.FeatureGroup(name="Regional Data Boxes", show=False)
    for region, config in REGIONS_CONFIG.items():
        color, anchor, center = config["color"], config["anchor"], config["center"]
        
        folium.PolyLine(locations=[anchor, center], color="#94A3B8", weight=2, dash_array="5, 5", opacity=0.9).add_to(infographic_group)
        folium.CircleMarker(location=center, radius=4, color="white", weight=1, fill=True, fill_color=color, fill_opacity=1).add_to(infographic_group)
        
        stud_val = student_data[region]
        stud_str = f"{stud_val:,}" if isinstance(stud_val, int) else stud_val
        
        box_html = f"""
        <div style="background: rgba(20, 20, 20, 0.92); border: 2px solid {color}; border-radius: 10px; padding: 12px 16px; font-family: 'Montserrat', sans-serif; color: white; box-shadow: 0 6px 20px rgba(0,0,0,0.6); min-width: 160px;">
            <div style="font-size: 14px; font-weight: 800; color: {color}; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 6px; margin-bottom: 8px;">● {region}</div>
            <div style="font-size: 13px; line-height: 1.6; font-weight: 600;">
                <div style="display: flex; justify-content: space-between;"><span>Branches:</span> <span style="color: #FFD700; margin-left: 12px;">{branch_counts[region]}</span></div>
                <div style="display: flex; justify-content: space-between;"><span>Schools:</span> <span style="color: #38BDF8; margin-left: 12px;">{school_counts[region]}</span></div>
                <div style="display: flex; justify-content: space-between;"><span>Students:</span> <span style="color: #39FF14; margin-left: 12px;">{stud_str}</span></div>
            </div>
        </div>
        """
        folium.Marker(location=anchor, icon=folium.DivIcon(html=box_html, icon_size=(180, 100), icon_anchor=(90, 50), class_name='infographic-element')).add_to(infographic_group)
    infographic_group.add_to(m)

    # All 53 Region Watermarks
    region_group = folium.FeatureGroup(name="Town & Region Labels", show=True)
    REGIONS_TOWNS = {
        "Woodlands": (1.436, 103.786), "Sembawang": (1.449, 103.818), "Yishun": (1.430, 103.835),
        "Mandai": (1.424, 103.811), "Simpang": (1.444, 103.844), "Lim Chu Kang": (1.433, 103.714),
        "Sungei Kadut": (1.414, 103.754), "Ang Mo Kio": (1.369, 103.845), "Hougang": (1.371, 103.892),
        "Sengkang": (1.392, 103.894), "Punggol": (1.405, 103.902), "Seletar": (1.408, 103.874),
        "Buangkok": (1.382, 103.893), "Serangoon": (1.355, 103.867), "Pasir Ris": (1.372, 103.947),
        "Tampines": (1.349, 103.943), "Bedok": (1.323, 103.927), "Changi": (1.365, 103.988),
        "Paya Lebar": (1.334, 103.888), "MacPherson": (1.326, 103.889), "Kembangan": (1.321, 103.912),
        "Simei": (1.343, 103.953), "Bishan": (1.352, 103.848), "Toa Payoh": (1.334, 103.856),
        "Central Area": (1.286, 103.854), "Kallang": (1.310, 103.865), "Geylang": (1.318, 103.887),
        "Marine Parade": (1.302, 103.904), "Bukit Timah": (1.329, 103.793), "Thomson": (1.361, 103.829),
        "Novena": (1.320, 103.843), "Newton": (1.312, 103.838), "Orchard": (1.303, 103.832),
        "River Valley": (1.297, 103.831), "Outram": (1.282, 103.839), "Marina Bay": (1.281, 103.856),
        "Mountbatten": (1.304, 103.884), "Balestier": (1.326, 103.851), "Potong Pasir": (1.331, 103.868),
        "Queenstown": (1.294, 103.806), "Bukit Merah": (1.281, 103.823), "Telok Blangah": (1.272, 103.809),
        "Sentosa": (1.249, 103.830), "Jurong West": (1.345, 103.705), "Jurong East": (1.333, 103.742),
        "Bukit Batok": (1.349, 103.749), "Bukit Panjang": (1.377, 103.771), "Choa Chu Kang": (1.385, 103.744),
        "Tengah": (1.364, 103.729), "Clementi": (1.316, 103.764), "West Coast": (1.303, 103.765),
        "Boon Lay": (1.338, 103.705), "Pioneer": (1.318, 103.697), "Tuas": (1.329, 103.636)
    }
    for town, (lat, lon) in REGIONS_TOWNS.items():
        folium.Marker(location=[lat, lon], icon=folium.DivIcon(html=f'<div class="region-label">{town}</div>'), interactive=False).add_to(region_group)
    region_group.add_to(m)

    # ==========================================
    # DIRECTORY SIDEBAR & LEGEND JS ENGINES
    # ==========================================
    sidebar_html = """
    <div id="sidebar-backdrop"></div>
    <button id="directory-btn">&#9776; Directory</button>
    <div id="side-panel">
        <div class="panel-header"><h2>Locations</h2><button id="close-panel">&times;</button></div>
        <div class="panel-content"><h3>Acer Academy Centers</h3><ul>
    """
    for name in sorted(EXISTING_BRANCHES.keys()): sidebar_html += f"<li>{name}</li>"
    sidebar_html += "</ul><h3>Institutions</h3>"
    
    category_colors = {"PRIMARY": "#38BDF8", "SECONDARY": "#A78BFA", "JUNIOR COLLEGE": "#FBBF24", "INTERNATIONAL": "#F472B6"}
    for cat, color in category_colors.items():
        if schools_dir[cat]:
            sidebar_html += f"<h4 style='color: {color};'>{cat.title()} ({len(schools_dir[cat])})</h4><ul>"
            for s_name in sorted(schools_dir[cat]): sidebar_html += f"<li>{s_name}</li>"
            sidebar_html += "</ul>"
    sidebar_html += """
        </div></div>
    <script>
        function closePanel() { document.getElementById('side-panel').classList.remove('open'); document.getElementById('sidebar-backdrop').classList.remove('open'); document.getElementById('directory-btn').style.opacity = '1'; document.getElementById('directory-btn').style.pointerEvents = 'auto'; }
        document.getElementById('directory-btn').addEventListener('click', function() { document.getElementById('side-panel').classList.add('open'); document.getElementById('sidebar-backdrop').classList.add('open'); this.style.opacity = '0'; this.style.pointerEvents = 'none'; });
        document.getElementById('close-panel').addEventListener('click', closePanel); document.getElementById('sidebar-backdrop').addEventListener('click', closePanel);
    </script>
    """
    m.get_root().html.add_child(Element(sidebar_html))

    legend_html = '''
    <div id="legend-box" style="position: fixed; bottom: 50px; left: 50px; width: 260px; background-color: rgba(20, 20, 20, 0.85); z-index:9999; font-size:14px; border: 1px solid rgba(255,255,255,0.15); border-radius: 16px; padding: 20px; color: #E0E0E0; box-shadow: 0 10px 30px rgba(0,0,0,0.6); font-family: 'Montserrat', sans-serif; backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); transition: all 0.3s ease;">
        <h4 style="margin-top:0; border-bottom:1px solid rgba(255,255,255,0.15); padding-bottom:12px; color: #00E5FF; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 14px;">Expansion Map</h4>
        <div style="display: flex; align-items: center; margin-bottom: 14px; margin-top: 15px;"><div style="background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); width: 22px; height: 22px; border-radius: 50%; border: 1px solid white; margin-right: 14px; display: flex; justify-content: center; align-items: center; overflow: hidden;"><img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%;"></div><span class="legend-text" style="font-weight: 600; color: white;">Acer Academy</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 14px;"><div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #00C9FF; margin-right: 14px; display: flex; align-items: center; justify-content: center;"><div id="legend-ring-inner" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div></div><span class="legend-text" style="color: white; font-weight: 500;">1.5km Radius Ring</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 14px;"><div style="background: linear-gradient(90deg, #00C9FF, #A78BFA, #F472B6); width: 22px; height: 12px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.5); margin-right: 14px;"></div><span class="legend-text" style="color: white; font-weight: 500;">Expansion Heatmap</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 14px;"><div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #39FF14; margin-right: 14px; display: flex; align-items: center; justify-content: center;"><div id="legend-ring-inner-sim" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div></div><span class="legend-text" style="color: white; font-weight: 500;">Simulated Zone (Click)</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 10px;"><div style="background: #38BDF8; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div><span class="legend-text" style="color: white; font-weight: 500;">Primary School</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 10px;"><div style="background: #A78BFA; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div><span class="legend-text" style="color: white; font-weight: 500;">Secondary School</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 10px;"><div style="background: #FBBF24; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div><span class="legend-text" style="color: white; font-weight: 500;">Junior College</span></div>
        <div style="display: flex; align-items: center; margin-bottom: 5px;"><div style="background: #F472B6; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div><span class="legend-text" style="color: white; font-weight: 500;">International School</span></div>
    </div>
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        var map = null;
        for (var key in window) { if (key.startsWith('map_')) { map = window[key]; break; } }
        if (map) {
            
            // Hard Boundary Lock - Traps camera over Singapore
            var sgBounds = L.latLngBounds([
                [1.15, 103.50], 
                [1.55, 104.10]
            ]);
            map.setMaxBounds(sgBounds);
            map.on('drag', function() {
                map.panInsideBounds(sgBounds, { animate: false });
            });

            var tilePane = document.querySelector('.leaflet-tile-pane');
            tilePane.style.filter = 'grayscale(100%) invert(100%) brightness(95%) contrast(115%)';
            document.querySelectorAll('.region-label').forEach(lbl => { lbl.style.color = '#ffffff'; lbl.style.textShadow = '-1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8)'; lbl.style.fontWeight = '700'; });

            var simActive = false, simLayer = null;
            map.on('overlayadd', function(e) { if (e.name && e.name.includes('Simulate New Branch')) { simActive = true; simLayer = e.layer; map.getContainer().style.cursor = 'crosshair'; map.doubleClickZoom.disable(); } });
            map.on('overlayremove', function(e) { if (e.name && e.name.includes('Simulate New Branch')) { simActive = false; map.getContainer().style.cursor = ''; map.doubleClickZoom.enable(); } });
            map.getContainer().addEventListener('click', function(e) {
                if (!simActive || !simLayer) return;
                if (e.target.closest && (e.target.closest('.leaflet-control-container') || e.target.closest('.leaflet-popup') || e.target.classList.contains('sim-circle'))) return;
                var latlng = map.mouseEventToLatLng(e);
                var circle = L.circle(latlng, { radius: 1500, color: '#39FF14', weight: 2.5, fillColor: '#39FF14', fillOpacity: 0.18, interactive: true, className: 'sim-circle' });
                circle.bindTooltip("<span style='font-size: 14px; font-weight: bold;'>Simulated Zone<br>👆 Click to remove</span>", {direction: 'top'});
                circle.on('click', function(ev) { L.DomEvent.stopPropagation(ev); simLayer.removeLayer(circle); });
                simLayer.addLayer(circle);
            }, true);

            map.on('baselayerchange', function(e) {
                var legend = document.getElementById('legend-box'), sidePanel = document.getElementById('side-panel'), title = legend ? legend.querySelector('h4') : null;
                var innerRing = document.getElementById('legend-ring-inner'), innerRingSim = document.getElementById('legend-ring-inner-sim'), spans = legend ? legend.querySelectorAll('span.legend-text') : [], regionLabels = document.querySelectorAll('.region-label');
                
                var isDarkStreets = (e.name === 'Dark Streets (Default)');
                var isExecDark = (e.name === 'Executive Dark Canvas (Clean)');
                var isDarkTheme = isDarkStreets || isExecDark;

                // Smart Checkbox Toggler! Auto-syncs the Leaflet UI Menu
                document.querySelectorAll('.leaflet-control-layers-selector').forEach(cb => {
                    const label = cb.nextElementSibling ? cb.nextElementSibling.textContent : cb.closest('label').textContent;
                    
                    if (isExecDark) {
                        // Turn ON Clean Mode Items
                        if ((label.includes('Regional Data Boxes') || label.includes('Regional Boundaries') || label.includes('Acer Academy Branches')) && !cb.checked) { cb.click(); }
                        // Turn OFF Noise
                        if ((label.includes('Schools') || label.includes('Heatmap') || label.includes('Town & Region Labels') || label.includes('Simulate')) && cb.checked) { cb.click(); }
                    } else {
                        // Restore Standard View
                        if (label.includes('Regional Data Boxes') && cb.checked) { cb.click(); }
                        if (label.includes('Schools') && !cb.checked) { cb.click(); }
                    }
                });

                if (isDarkStreets) {
                    tilePane.style.filter = 'grayscale(100%) invert(100%) brightness(95%) contrast(115%)';
                } else if (isExecDark) {
                    tilePane.style.filter = 'none'; // dark_matter is naturally black, don't invert it!
                } else {
                    tilePane.style.filter = 'none';
                }

                if (isDarkTheme) {
                    if (legend) { 
                        legend.style.display = isExecDark ? 'none' : 'block';
                        legend.style.backgroundColor = 'rgba(20, 20, 20, 0.85)'; legend.style.borderColor = 'rgba(255,255,255,0.15)'; title.style.color = '#00E5FF'; title.style.borderBottom = '1px solid rgba(255,255,255,0.15)'; spans.forEach(s => s.style.color = 'white'); if (innerRing) innerRing.style.backgroundColor = 'rgba(20, 20, 20, 0.85)'; if (innerRingSim) innerRingSim.style.backgroundColor = 'rgba(20, 20, 20, 0.85)'; 
                    }
                    if (sidePanel) { sidePanel.style.backgroundColor = 'rgba(20, 20, 20, 0.90)'; var spTitle = sidePanel.querySelector('.panel-header h2'); if (spTitle) spTitle.style.color = '#00E5FF'; sidePanel.querySelectorAll('li').forEach(li => li.style.color = 'rgba(255,255,255,0.8)'); }
                    regionLabels.forEach(lbl => { lbl.style.color = '#ffffff'; lbl.style.textShadow = '-1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8)'; lbl.style.fontWeight = '700'; });
                } else {
                    if (legend) { 
                        legend.style.display = 'block';
                        legend.style.backgroundColor = 'rgba(255, 255, 255, 0.9)'; legend.style.borderColor = '#ccc'; title.style.color = '#111'; title.style.borderBottom = '1px solid #ccc'; spans.forEach(s => s.style.color = '#333'); if (innerRing) innerRing.style.backgroundColor = 'rgba(255, 255, 255, 0.8)'; if (innerRingSim) innerRingSim.style.backgroundColor = 'rgba(255, 255, 255, 0.8)'; 
                    }
                    if (sidePanel) { sidePanel.style.backgroundColor = 'rgba(255, 255, 255, 0.95)'; var spTitle = sidePanel.querySelector('.panel-header h2'); if (spTitle) spTitle.style.color = '#111'; sidePanel.querySelectorAll('li').forEach(li => li.style.color = '#333'); }
                    regionLabels.forEach(lbl => { lbl.style.color = '#111111'; lbl.style.textShadow = '-1px -1px 3px #fff, 1px -1px 3px #fff, -1px 1px 3px #fff, 1px 1px 3px #fff, 0px 0px 15px rgba(255,255,255,0.8)'; lbl.style.fontWeight = '800'; });
                }
            });
        }
    });
    </script>
    '''
    m.get_root().html.add_child(Element(legend_html))
    folium.LayerControl(position='topright').add_to(m)
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Master interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
