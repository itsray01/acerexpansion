import json
import os
import math
import random
import requests
import pandas as pd
import folium
from folium import plugins, Element
from folium.plugins import HeatMap

# ==========================================
# 1. CONFIGURATION
# ==========================================
SCHOOL_DB_PATH = "All_Schools_Geocoded.csv" # Upgraded to use the new CSV
URA_REGIONS_PATH = "ura_regions.json"
OUTPUT_MAP_PATH = "acer_expansion_map.html"

# Your Existing Branches (Updated with highly precise GPS coordinates)
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
# 2. SMART DATA LOADER (PANDAS)
# ==========================================
def get_col(columns, keywords, exclude_keywords=[]):
    """Fuzzy matching for column headers."""
    for col in columns:
        col_lower = col.lower().strip()
        if any(kw in col_lower for kw in keywords):
            if not any(ex in col_lower for ex in exclude_keywords):
                return col
    return None

def load_schools_from_csv(filepath):
    if not os.path.exists(filepath):
        print(f"[!] Warning: {filepath} not found. Run geocoder first!")
        return []
    
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"[!] Error reading CSV: {e}")
        return []

    cols = list(df.columns)
    lat_col = get_col(cols, ["lat", "y", "latitude"])
    lon_col = get_col(cols, ["lon", "long", "longitude", "x"])
    name_col = get_col(cols, ["name", "school", "institution"])
    tier_col = get_col(cols, ["tier", "rank", "category"])
    level_col = get_col(cols, ["level", "education", "type"])
    
    url_col = get_col(cols, ["url", "web", "http", "link", "website"])
    addr_col = get_col(cols, ["address", "street", "addr", "location"], exclude_keywords=["url", "web", "http", "link"])
    region_col = get_col(cols, ["region", "zone", "area", "sector"])

    schools = []
    for idx, row in df.iterrows():
        try:
            val_lat = str(row[lat_col]).strip()
            val_lon = str(row[lon_col]).strip()
            if not val_lat or not val_lon or val_lat.lower() in ['nan', '']: continue
            
            # Micro-jitter (~150m scatter) to prevent overlapping dots
            jitter_lat = float(val_lat) + random.uniform(-0.0015, 0.0015)
            jitter_lon = float(val_lon) + random.uniform(-0.0015, 0.0015)
            
            name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Unknown School"
            tier = str(row[tier_col]).strip() if tier_col and pd.notna(row[tier_col]) else ""
            level = str(row[level_col]).strip() if level_col and pd.notna(row[level_col]) else "General"
            addr = str(row[addr_col]).strip() if addr_col and pd.notna(row[addr_col]) else "Address unavailable"
            url = str(row[url_col]).strip() if url_col and pd.notna(row[url_col]) else ""
            region = str(row[region_col]).strip() if region_col and pd.notna(row[region_col]) else "Singapore"

            schools.append({
                "name": name, "lat": jitter_lat, "lon": jitter_lon,
                "tier": tier, "level": level, "address": addr, "url": url, "region": region
            })
        except ValueError:
            continue
            
    print(f"[*] Successfully loaded {len(schools)} schools from CSV.")
    return schools

# ==========================================
# 3. MAP GENERATION
# ==========================================
def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools_from_csv(SCHOOL_DB_PATH)
    if not schools: return
    
    # Initialize the map with 'tiles=None' so we can explicitly order our base maps
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles=None, max_bounds=True, min_lat=1.15, max_lat=1.48, min_lon=103.58, max_lon=104.05)
    
    # Base Maps
    folium.TileLayer('CartoDB dark_matter', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='Executive Dark Canvas (Clean)', show=False).add_to(m)

    # ----------------------------------------------------
    # YOUR EXACT CSS (UNTOUCHED)
    # ----------------------------------------------------
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    /* Global Tooltip Styling */
    .leaflet-tooltip {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        padding: 10px 14px !important;
        background-color: rgba(20, 20, 20, 0.95) !important;
        color: white !important;
        border: 1px solid #888 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    }
    .leaflet-popup-content { font-family: 'Montserrat', sans-serif !important; font-size: 14px !important; line-height: 1.4 !important; }

    /* ====================================================
       OVERHAUL: CUSTOM BRANDED TRANSLUCENT LAYERS MENU
       ==================================================== */
    
    .leaflet-control-layers {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
        padding: 15px !important;
        margin-top: -15px !important;
        margin-right: -15px !important;
    }

    .leaflet-touch .leaflet-control-layers-toggle,
    .leaflet-retina .leaflet-control-layers-toggle,
    .leaflet-control-layers-toggle {
        margin-left: auto !important; 
        background-image: url('https://i.imgur.com/YhyOq9V.png') !important;
        background-size: 65% !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-color: rgba(25, 25, 25, 0.85) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border-radius: 14px !important;
        width: 55px !important;
        height: 55px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.5) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        transition: all 0.3s ease !important;
    }
    
    .leaflet-control-layers-toggle:hover {
        background-color: rgba(40, 40, 40, 0.95) !important;
        transform: scale(1.05) !important;
        border-color: #00E5FF !important;
    }

    .leaflet-control-layers-toggle span { display: none !important; }

    .leaflet-control-layers.leaflet-control-layers-expanded {
        margin-top: 5px !important;
        background: rgba(20, 20, 20, 0.85) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 18px !important;
        padding: 22px 28px !important;
        font-family: 'Montserrat', sans-serif !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important;
        min-width: 230px !important;
    }

    .leaflet-control-layers-list::before {
        content: "Map Display Settings";
        display: block;
        font-size: 15px;
        font-weight: 700;
        color: #00E5FF;
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 15px;
        border-bottom: 1px solid rgba(255,255,255,0.15);
        padding-bottom: 10px;
    }

    .leaflet-control-layers-list { font-size: 14px !important; margin-bottom: 0 !important; }
    
    .leaflet-control-layers-base label,
    .leaflet-control-layers-overlays label {
        display: flex !important;
        align-items: center !important;
        margin: 14px 0 !important;
        cursor: pointer !important;
        font-weight: 500 !important;
        transition: color 0.2s !important;
    }

    .leaflet-control-layers-base label:hover,
    .leaflet-control-layers-overlays label:hover { color: #FFD700 !important; }
    .leaflet-control-layers-separator { border-top: 1px solid rgba(255,255,255,0.15) !important; margin: 18px 0 !important; }

    input[type="checkbox"].leaflet-control-layers-selector,
    input[type="radio"].leaflet-control-layers-selector {
        appearance: none; -webkit-appearance: none;
        width: 18px !important; height: 18px !important;
        border: 2px solid #888 !important; border-radius: 4px;
        margin-right: 12px !important; cursor: pointer !important;
        position: relative; background: rgba(255,255,255,0.1); transition: all 0.2s;
    }
    input[type="radio"].leaflet-control-layers-selector { border-radius: 50%; }
    input[type="checkbox"].leaflet-control-layers-selector:checked,
    input[type="radio"].leaflet-control-layers-selector:checked { background: #00E5FF !important; border-color: #00E5FF !important; }
    
    input[type="checkbox"].leaflet-control-layers-selector:checked::after {
        content: "✔"; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #000; font-size: 12px; font-weight: bold;
    }
    input[type="radio"].leaflet-control-layers-selector:checked::after {
        content: ""; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 8px; height: 8px; background: #000; border-radius: 50%;
    }

    /* ====================================================
       HIGH-CONTRAST REGION LABELS
       ==================================================== */
    .region-label {
        position: relative !important;
        z-index: 9999 !important;
        font-family: 'Montserrat', sans-serif !important;
        font-size: 13px !important;
        text-transform: uppercase !important;
        letter-spacing: 3.5px !important;
        white-space: nowrap !important;
        pointer-events: none !important; 
        transform: translate(-50%, -50%) !important;
        transition: all 0.2s ease !important;
    }
    
    /* ====================================================
       SLIDE-OUT DIRECTORY SIDEBAR & BACKDROP
       ==================================================== */
    #sidebar-backdrop {
        position: fixed; top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.5); z-index: 99998; opacity: 0; pointer-events: none; transition: opacity 0.3s;
    }
    #sidebar-backdrop.open { opacity: 1; pointer-events: auto; }
    
    #directory-btn {
        position: fixed; bottom: 30px; right: 20px; z-index: 9997;
        background-color: rgba(25, 25, 25, 0.85); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2); color: white; padding: 12px 18px; border-radius: 8px;
        font-family: 'Montserrat', sans-serif; font-weight: 600; font-size: 14px; cursor: pointer;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5); transition: all 0.3s; display: flex; align-items: center; gap: 8px;
    }
    #directory-btn:hover { background-color: rgba(40,40,40,0.95); border-color: #00E5FF; color: #00E5FF; transform: translateY(-2px); }
    
    #side-panel {
        position: fixed; top: 0; right: -400px; width: 320px; height: 100vh;
        background-color: rgba(20, 20, 20, 0.90); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px);
        border-left: 1px solid rgba(255,255,255,0.1); z-index: 99999;
        transition: right 0.4s cubic-bezier(0.25, 0.8, 0.25, 1); color: white;
        font-family: 'Montserrat', sans-serif; display: flex; flex-direction: column;
        box-shadow: -5px 0 30px rgba(0,0,0,0.6); overflow: hidden;
    }
    #side-panel.open { right: 0; }
    
    .panel-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 20px 25px; border-bottom: 1px solid rgba(255,255,255,0.1); flex-shrink: 0;
    }
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

    # ----------------------------------------------------
    # CHOROPLETH REGIONS (Restored from your screenshot)
    # ----------------------------------------------------
    fg_regions = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True).add_to(m)
    if os.path.exists(URA_REGIONS_PATH):
        try:
            with open(URA_REGIONS_PATH, "r") as f:
                geo_data = json.load(f)
            def style_function(feature):
                region_name = feature.get("properties", {}).get("REGION_N", "").upper()
                if 'NORTH-EAST' in region_name or 'NORTH' in region_name: color = '#1f77b4'
                elif 'WEST' in region_name: color = '#2ca02c'
                elif 'EAST' in region_name: color = '#ff7f0e'
                else: color = '#d62728' 
                # FIX: Removed the jagged white border lines so the regions blend smoothly
                return {"fillColor": color, "color": color, "weight": 0.5, "fillOpacity": 0.20}
            folium.GeoJson(geo_data, style_function=style_function, name="Regional Boundaries").add_to(fg_regions)
        except Exception as e:
            print(f"[!] Could not load GeoJSON: {e}")

    # ==========================================
    # DIRECTORY DATA STRUCTURE (For Side Panel)
    # ==========================================
    schools_dir = {"PRIMARY": [], "SECONDARY": [], "JUNIOR COLLEGE": [], "INTERNATIONAL": []}

    print(f"[*] Plotting {len(schools)} schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)")
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)")
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)")
    fg_heatmap = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False).add_to(m)
    
    heat_data = []

    for school in schools:
        level = school.get("level", "").upper()
        lat = school["lat"]
        lon = school["lon"]
        name = school["name"]
        
        heat_data.append([lat, lon, 1.0])
        
        # Categorize for the map pins AND the directory panel
        if "PRIMARY" in level:
            fill_color = "#38BDF8" # Sky Blue
            group = primary_group
            schools_dir["PRIMARY"].append(name)
        elif "SECONDARY" in level:
            fill_color = "#A78BFA" # Soft Violet
            group = secondary_group
            schools_dir["SECONDARY"].append(name)
        elif "JUNIOR COLLEGE" in level or "PRE-U" in level:
            fill_color = "#FBBF24" # Golden Amber
            group = jc_group
            schools_dir["JUNIOR COLLEGE"].append(name)
        elif "INTERNATIONAL" in level:
            fill_color = "#F472B6" # Rose Pink
            group = intl_group
            schools_dir["INTERNATIONAL"].append(name)
        else:
            continue # Skip "Other Institutes" entirely!
            
        # Hide standard tier logic
        tier_badge = ""
        if school["tier"] and school["tier"].lower() not in ["standard", ""]:
            tier_badge = f"""<div style="background:#ffd700; color:#000; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold; display:inline-block; margin-bottom:8px;">★ TIER: {school['tier'].upper()}</div>"""

        url_link = f"""<div style="margin-top:6px;"><a href="{school['url']}" target="_blank" style="color:#38b6ff; text-decoration:none; font-size:11px;">Visit Website ↗</a></div>""" if school["url"] else ""

        popup_html = f"""
        <div style="font-family: 'Montserrat', sans-serif; min-width: 220px; padding: 4px;">
            <div style="font-size: 13px; font-weight: bold; color: {fill_color}; margin-bottom: 6px; text-transform: uppercase;">{name}</div>
            {tier_badge}
            <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;"><b>Level:</b> {level.title()} | <b>Region:</b> {school['region'].title()}</div>
            <div style="font-size: 11px; color: #fff; background: #2a2a32; padding: 6px; border-radius: 4px;">📍 <b>Addr:</b> {school['address']}</div>
            {url_link}
        </div>
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=7, 
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"<span style='font-size: 14px;'>{name}</span>",
            color="white",
            weight=1,
            fill_color=fill_color,
            fill=True,
            fill_opacity=0.85
        ).add_to(group)
        
    primary_group.add_to(m)
    secondary_group.add_to(m)
    jc_group.add_to(m)
    intl_group.add_to(m)

    # Add vibrant HeatMap
    if heat_data:
        HeatMap(heat_data, radius=18, blur=12, min_opacity=0.4, gradient={0.2: '#0000ff', 0.4: '#00ffff', 0.6: '#00ff00', 0.8: '#ffff00', 1.0: '#ff0000'}).add_to(fg_heatmap)

    # ----------------------------------------------------
    # YOUR EXACT ACER BRANCH LOGOS
    # ----------------------------------------------------
    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & 1.5km Radius Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        # FIX: Replaced the broken red image with a sleek, premium dark marker and a cyan star
        icon_html = f"""
        <div style="
            background: #151515;
            border: 2px solid #00E5FF;
            border-radius: 50%;
            width: 28px;
            height: 28px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #00E5FF;
            font-size: 14px;
            box-shadow: 0 0 15px rgba(0, 229, 255, 0.6);
        ">★</div>
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #00E5FF;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 16px; font-weight: bold; white-space: nowrap;'>★ {name}</span>",
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
        ).add_to(branch_group)
        
        # FIX: Forced the 1.5km radius rings to be Electric Cyan
        folium.Circle(
            location=[lat, lon],
            radius=1500, # 1.5km in meters
            color="#00C9FF", # Premium Glowing Electric Cyan
            weight=2,
            fill_color="#00C9FF",
            fill_opacity=0.15
        ).add_to(branch_group)
    branch_group.add_to(m)

    # ----------------------------------------------------
    # REGIONAL DATA BOXES (Business Times Callouts)
    # ----------------------------------------------------
    fg_data_boxes = folium.FeatureGroup(name="Regional Data Boxes", show=True).add_to(m)
    infographic_boxes = [
        {"region": "WEST", "center": [1.3400, 103.7100], "box": [1.3200, 103.6200], "color": "#4ADE80", "b": 3, "s": 83, "st": "115,500"},
        {"region": "NORTH", "center": [1.4300, 103.8100], "box": [1.4700, 103.8300], "color": "#38BDF8", "b": 5, "s": 124, "st": "172,200"},
        {"region": "EAST", "center": [1.3500, 103.9400], "box": [1.4000, 103.9800], "color": "#FBBF24", "b": 4, "s": 47, "st": "64,500"},
        {"region": "CENTRAL", "center": [1.2900, 103.8200], "box": [1.2200, 103.8200], "color": "#F87171", "b": 5, "s": 83, "st": "115,500"}
    ]
    for b in infographic_boxes:
        folium.PolyLine(locations=[b["box"], b["center"]], color=b["color"], weight=1.5, opacity=0.8, dash_array="4").add_to(fg_data_boxes)
        box_html = f"""
        <div style="background: rgba(15, 15, 18, 0.95); border: 1px solid {b['color']}; border-radius: 6px; padding: 12px; width: 140px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); backdrop-filter: blur(8px); font-family: 'Montserrat', sans-serif;">
            <div style="color: {b['color']}; font-weight: 800; font-size: 10px; margin-bottom: 8px; letter-spacing: 1px; display: flex; align-items: center; gap: 6px; text-transform: uppercase;"><div style="width:6px; height:6px; background:{b['color']};"></div> {b['region']}</div>
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: #A0AEC0; margin-bottom: 5px;"><span>Branches:</span> <b style="color: #FACC15;">{b['b']}</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: #A0AEC0; margin-bottom: 5px;"><span>Schools:</span> <b style="color: #38BDF8;">{b['s']}</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 9px; color: #A0AEC0;"><span>Students:</span> <b style="color: #4ADE80;">{b['st']}</b></div>
        </div>"""
        folium.Marker(location=b["box"], icon=folium.DivIcon(html=box_html, icon_size=(140, 80), icon_anchor=(70, 40))).add_to(fg_data_boxes)


    # ==========================================
    # INJECT REGION WATERMARKS
    # ==========================================
    print(f"[*] Injecting Extended Region Watermarks...")
    region_group = folium.FeatureGroup(name="Town & Region Labels", show=True)
    
    REGIONS = {
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

    for region, (lat, lon) in REGIONS.items():
        folium.Marker(
            location=[lat, lon],
            icon=folium.DivIcon(html=f'<div class="region-label">{region}</div>'),
            interactive=False
        ).add_to(region_group)
    region_group.add_to(m)
    
    # ----------------------------------------------------
    # YOUR EXACT SIDEBAR HTML + TOP RIGHT ACER DASHBOARD
    # ----------------------------------------------------
    sidebar_html = f"""
    <!-- Top-Right Acer Dashboard Injection -->
    <div style="position: absolute; top: 20px; right: 20px; z-index: 1000; background: rgba(15, 15, 18, 0.95); border: 1px solid #333; border-radius: 12px; padding: 16px; width: 260px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); backdrop-filter: blur(8px); font-family: 'Montserrat', sans-serif; pointer-events: none;">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
            <div style="background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); width: 36px; height: 36px; border-radius: 8px; border: 2px solid #FFF; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px rgba(255,255,255,0.4); overflow: hidden;">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%;">
            </div>
            <div style="line-height: 1.1;">
                <div style="color: #FFF; font-weight: 900; font-size: 18px; letter-spacing: 1px;">ACER</div>
                <div style="color: #ff3344; font-weight: 800; font-size: 11px; letter-spacing: 2px;">EXPANSION</div>
            </div>
        </div>
        <div style="color: #A0AEC0; font-size: 11px; line-height: 1.5; margin-bottom: 16px;">
            Analyzing <b style="color: #FFF;">{len(schools)}</b> educational zones across <b style="color: #FFF;">{len(EXISTING_BRANCHES)}</b> active branches.
        </div>
        <div>
            <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 6px;">
                <div style="color: #718096; font-size: 9px; font-weight: 700; letter-spacing: 1px;">NETWORK STATUS</div>
                <div style="color: #4ADE80; font-size: 11px; font-weight: 800;">Total Coverage</div>
            </div>
            <div style="background: #2D3748; height: 4px; border-radius: 2px; width: 100%; overflow: hidden;">
                <div style="background: #4ADE80; height: 100%; width: 100%; box-shadow: 0 0 10px #4ADE80;"></div>
            </div>
        </div>
    </div>

    <!-- Directory Sidebar -->
    <div id="sidebar-backdrop"></div>
    <button id="directory-btn">&#9776; Directory</button>
    <div id="side-panel">
        <div class="panel-header">
            <h2>Locations</h2>
            <button id="close-panel">&times;</button>
        </div>
        <div class="panel-content">
            <h3>Acer Academy Centers</h3>
            <ul>
    """
    for name in sorted(EXISTING_BRANCHES.keys()):
        sidebar_html += f"<li>{name}</li>"
    sidebar_html += "</ul><h3>Institutions</h3>"
    
    category_colors = {"PRIMARY": "#38BDF8", "SECONDARY": "#A78BFA", "JUNIOR COLLEGE": "#FBBF24", "INTERNATIONAL": "#F472B6"}
    for category, cat_color in category_colors.items():
        if schools_dir[category]:
            sidebar_html += f"<h4 style='color: {cat_color};'>{category.title()} ({len(schools_dir[category])})</h4><ul>"
            for school_name in sorted(schools_dir[category]):
                sidebar_html += f"<li>{school_name}</li>"
            sidebar_html += "</ul>"
            
    sidebar_html += """
        </div>
    </div>
    <script>
        function closePanel() {
            document.getElementById('side-panel').classList.remove('open');
            document.getElementById('sidebar-backdrop').classList.remove('open');
            document.getElementById('directory-btn').style.opacity = '1';
            document.getElementById('directory-btn').style.pointerEvents = 'auto';
        }
        
        document.getElementById('directory-btn').addEventListener('click', function() {
            document.getElementById('side-panel').classList.add('open');
            document.getElementById('sidebar-backdrop').classList.add('open');
            this.style.opacity = '0';
            this.style.pointerEvents = 'none';
        });
        
        document.getElementById('close-panel').addEventListener('click', closePanel);
        document.getElementById('sidebar-backdrop').addEventListener('click', closePanel);
    </script>
    """
    m.get_root().html.add_child(Element(sidebar_html))

    # ----------------------------------------------------
    # YOUR EXACT LEGEND HTML + JS LOGIC
    # ----------------------------------------------------
    legend_html = '''
    <div id="legend-box" style="
        position: fixed; 
        bottom: 50px; left: 50px; width: 260px; height: auto; 
        background-color: rgba(20, 20, 20, 0.85); z-index:9999; font-size:14px;
        border: 1px solid rgba(255,255,255,0.15); border-radius: 16px; padding: 20px; color: #E0E0E0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6); font-family: 'Montserrat', sans-serif;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        transition: all 0.3s ease;
        ">
        <h4 style="margin-top:0; border-bottom:1px solid rgba(255,255,255,0.15); padding-bottom:12px; color: #00E5FF; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 14px;">Expansion Map</h4>
        
        <div style="display: flex; align-items: center; margin-bottom: 14px; margin-top: 15px;">
            <div style="background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); width: 22px; height: 22px; border-radius: 50%; border: 1px solid white; margin-right: 14px; display: flex; justify-content: center; align-items: center; overflow: hidden; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%;">
            </div>
            <span class="legend-text" style="font-weight: 600; color: white;">Acer Academy</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 18px;">
            <div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #00C9FF; margin-right: 14px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <div id="legend-ring-inner" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div>
            </div>
            <span class="legend-text" style="color: white; font-weight: 500;">1.5km Radius Ring</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: #38BDF8; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">Primary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: #A78BFA; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">Secondary School</span>
        </div>

        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: #FBBF24; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">Junior College</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="background: #F472B6; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">International School</span>
        </div>
    </div>
    
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        var map = null;
        for (var key in window) {
            if (key.startsWith('map_')) { map = window[key]; break; }
        }
        if (map) {
            var tilePane = document.querySelector('.leaflet-tile-pane');
            
            // Set default styling on initial load (Dark Mode)
            tilePane.style.filter = 'grayscale(100%) invert(100%) brightness(95%) contrast(115%)';
            document.querySelectorAll('.region-label').forEach(lbl => {
                lbl.style.color = '#ffffff';
                lbl.style.textShadow = '-1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8)';
                lbl.style.fontWeight = '700';
            });

            map.on('baselayerchange', function(e) {
                var legend = document.getElementById('legend-box');
                var sidePanel = document.getElementById('side-panel');
                var title = legend ? legend.querySelector('h4') : null;
                var innerRing = document.getElementById('legend-ring-inner');
                var spans = legend ? legend.querySelectorAll('span.legend-text') : [];
                var regionLabels = document.querySelectorAll('.region-label');
                
                var isDark = (e.name === 'Dark Streets (Default)' || e.name === 'Executive Dark Canvas (Clean)');

                if (isDark) {
                    // Dark Mode Logic
                    tilePane.style.filter = 'grayscale(100%) invert(100%) brightness(95%) contrast(115%)';
                    if (legend) {
                        legend.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                        legend.style.borderColor = 'rgba(255,255,255,0.15)';
                        title.style.color = '#00E5FF';
                        title.style.borderBottom = '1px solid rgba(255,255,255,0.15)';
                        spans.forEach(s => s.style.color = 'white');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                    }
                    if (sidePanel) {
                        sidePanel.style.backgroundColor = 'rgba(20, 20, 20, 0.90)';
                        var spTitle = sidePanel.querySelector('.panel-header h2');
                        if (spTitle) spTitle.style.color = '#00E5FF';
                        var spListItems = sidePanel.querySelectorAll('li');
                        spListItems.forEach(li => li.style.color = 'rgba(255,255,255,0.8)');
                    }
                    // Dark Mode Labels: Bright White with Bold Black Outline/Shadow
                    regionLabels.forEach(lbl => {
                        lbl.style.color = '#ffffff';
                        lbl.style.textShadow = '-1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8)';
                        lbl.style.fontWeight = '700';
                    });
                } else {
                    // Light Mode / Standard OSM Logic
                    tilePane.style.filter = 'none'; // Strips filters for full color OpenStreetMap!
                    
                    if (legend) {
                        legend.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                        legend.style.borderColor = '#ccc';
                        title.style.color = '#111';
                        title.style.borderBottom = '1px solid #ccc';
                        spans.forEach(s => s.style.color = '#333');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                    }
                    if (sidePanel) {
                        sidePanel.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
                        var spTitle = sidePanel.querySelector('.panel-header h2');
                        if (spTitle) spTitle.style.color = '#111';
                        var spListItems = sidePanel.querySelectorAll('li');
                        spListItems.forEach(li => li.style.color = '#333');
                    }
                    // Light Mode Labels: Bold Black with Thick White Outline/Shadow
                    regionLabels.forEach(lbl => {
                        lbl.style.color = '#111111';
                        lbl.style.textShadow = '-1px -1px 3px #fff, 1px -1px 3px #fff, -1px 1px 3px #fff, 1px 1px 3px #fff, 0px 0px 15px rgba(255,255,255,0.8)';
                        lbl.style.fontWeight = '800';
                    });
                }
            });
        }
    });
    </script>
    '''
    m.get_root().html.add_child(Element(legend_html))
    
    # Add a Layer Control panel
    folium.LayerControl(collapsed=False).add_to(m)
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
