import json
import os
import random
import requests
import folium
from folium import plugins
from folium.element import Element

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
SCHOOL_DB_PATH = "school_db.json"
OUTPUT_MAP_PATH = "acer_expansion_map.html"

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

def load_schools():
    if not os.path.exists(SCHOOL_DB_PATH):
        print(f"[!] Cannot find {SCHOOL_DB_PATH}. Run build_school_db.py first!")
        return []
    with open(SCHOOL_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    if not schools: return
    
    # Initialize the map with explicit tiles=None to order custom base maps
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles=None)
    
    # Native Dark Mode Base Map (No glitchy CSS filters needed)
    folium.TileLayer('CartoDB dark_matter', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)

    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    /* Tooltip Styling */
    .leaflet-tooltip {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 15px !important; font-weight: 600 !important;
        padding: 10px 14px !important; background-color: rgba(20, 20, 20, 0.95) !important;
        color: white !important; border: 1px solid #888 !important; border-radius: 8px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    }
    .leaflet-popup-content { font-family: 'Montserrat', sans-serif !important; font-size: 14px !important; }

    /* Custom Layer Control Menu */
    .leaflet-control-layers {
        border: none !important; background: transparent !important; box-shadow: none !important;
        padding: 15px !important; margin-top: -15px !important; margin-right: -15px !important;
    }
    .leaflet-control-layers-toggle {
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
    .leaflet-control-layers-toggle span { display: none !important; }
    .leaflet-control-layers.leaflet-control-layers-expanded {
        margin-top: 5px !important; background: rgba(20, 20, 20, 0.85) !important;
        backdrop-filter: blur(16px) !important; color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 18px !important;
        padding: 22px 28px !important; font-family: 'Montserrat', sans-serif !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important; min-width: 230px !important;
    }

    /* Checkboxes */
    input[type="checkbox"].leaflet-control-layers-selector, input[type="radio"].leaflet-control-layers-selector {
        appearance: none; -webkit-appearance: none; width: 18px !important; height: 18px !important;
        border: 2px solid #888 !important; border-radius: 4px; margin-right: 12px !important;
        cursor: pointer !important; position: relative; background: rgba(255,255,255,0.1);
    }
    input[type="radio"].leaflet-control-layers-selector { border-radius: 50%; }
    input[type="checkbox"].leaflet-control-layers-selector:checked, input[type="radio"].leaflet-control-layers-selector:checked { 
        background: #00E5FF !important; border-color: #00E5FF !important; 
    }
    input[type="checkbox"].leaflet-control-layers-selector:checked::after {
        content: "✔"; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #000; font-size: 12px; font-weight: bold;
    }

    /* High Contrast Region Labels */
    .region-label {
        font-family: 'Montserrat', sans-serif !important; font-size: 13px !important; text-transform: uppercase !important;
        letter-spacing: 3.5px !important; white-space: nowrap !important; pointer-events: none !important; 
        color: #ffffff !important;
        text-shadow: -1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8) !important;
        font-weight: 700 !important;
    }
    
    /* Executive Dashboard (Top Right) */
    .acer-dashboard {
        position: fixed; top: 20px; right: 80px; z-index: 9999;
        background: rgba(20,20,20,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.15);
        color: white; font-family: 'Montserrat', sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 280px;
    }
    .acer-dashboard h4 { margin: 0 0 15px 0; font-size: 16px; font-weight: 800; display: flex; align-items: center; gap: 10px; }
    .acer-stat { font-size: 12px; color: #ccc; line-height: 1.5; }
    .progress-bar-bg { width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; margin-top: 5px; overflow: hidden; }
    .progress-bar-fill { width: 100%; height: 100%; background: #4ADE80; border-radius: 3px; }

    /* DATA BOXES */
    .data-box {
        position: fixed; z-index: 9999; background: rgba(15,15,15,0.95);
        padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1);
        color: white; font-family: 'Montserrat', sans-serif; width: 180px;
        box-shadow: 0 8px 20px rgba(0,0,0,0.6); backdrop-filter: blur(8px);
    }
    .data-box-title { font-size: 13px; font-weight: 800; margin-bottom: 10px; text-transform: uppercase; letter-spacing: 1px; color: #fff; }
    .data-box-row { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa; }
    .data-box-row b { color: #00E5FF; }

    /* LEADER LINES */
    .connecting-line { position: fixed; z-index: 9998; background: transparent; border-top: 2px dashed rgba(255,255,255,0.4); }
    .connecting-line.vertical { border-top: none; border-left: 2px dashed rgba(255,255,255,0.4); }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    print("[*] Plotting URA Regions...")
    if os.path.exists("ura_regions.json"):
        folium.GeoJson(
            "ura_regions.json",
            name="Regional Boundaries (Choropleth)",
            style_function=lambda feature: {
                'fillColor': feature['properties'].get('fill', '#333333') if 'properties' in feature and 'fill' in feature['properties'] else '#333333',
                'color': 'transparent', # Removing jagged white strokes
                'weight': 0,
                'fillOpacity': 0.35
            }
        ).add_to(m)

    print("[*] Plotting Expansion Heatmap...")
    heat_data = [[s['lat'], s['lon']] for s in schools if 'lat' in s and 'lon' in s]
    # Huge 3.0km simulated heatmap spread
    plugins.HeatMap(heat_data, name="Expansion Heatmap (Untapped)", radius=45, blur=35, show=False).add_to(m)

    print(f"[*] Plotting {len(schools)} schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)")
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)")
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)")
    
    for school in schools:
        level = school.get("level", "").upper()
        # Micro-jitter prevents exact stacking of pins
        lat = school["lat"] + random.uniform(-0.0005, 0.0005)
        lon = school["lon"] + random.uniform(-0.0005, 0.0005)
        name = school["name"]
        
        if "PRIMARY" in level:
            fill_color = "#38BDF8"
            group = primary_group
        elif "SECONDARY" in level:
            fill_color = "#A78BFA"
            group = secondary_group
        elif "JUNIOR COLLEGE" in level:
            fill_color = "#FBBF24"
            group = jc_group
        elif "INTERNATIONAL" in level:
            fill_color = "#F472B6"
            group = intl_group
        else:
            continue
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=6, 
            popup=f"<b style='color: {fill_color}'>{name}</b><br>{level.title()}",
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

    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        # Pure transparent background, loading Imgur link perfectly
        icon_html = '''
        <div style="background-color: transparent; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 2px solid #ffffff; border-radius: 8px; box-shadow: 0 4px 10px rgba(0,0,0,0.5);">
            <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; height: 100%; object-fit: cover;">
        </div>
        '''
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #00E5FF;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 16px; font-weight: bold;'>★ {name}</span>",
            icon=folium.DivIcon(html=icon_html, icon_size=(32, 32), icon_anchor=(16, 16))
        ).add_to(branch_group)
        
        # Proper Cyan Color for active 1.5km radius ring
        folium.Circle(
            location=[lat, lon],
            radius=1500,
            popup=f"1.5km Radius Ring for {name}",
            color="#00C9FF", 
            weight=2,
            fill_color="#00C9FF",
            fill_opacity=0.15
        ).add_to(branch_group)
    branch_group.add_to(m)

    print(f"[*] Injecting Region Watermarks...")
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

    
    # Notice: Pure string concatenation to strictly avoid { } variable brace conflicts in CSS!
    dashboard_html = """
    <div class="acer-dashboard">
        <h4>
            <div style="background-color: transparent; border-radius: 6px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #fff;">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <span>ACER <span style="color:#ff3344;">EXPANSION</span></span>
        </h4>
        <div class="acer-stat">Analyzing <b style="color:#fff;">""" + str(len(schools)) + """</b> educational zones across <b style="color:#fff;">""" + str(len(EXISTING_BRANCHES)) + """</b> active branches.</div>
        <div style="display:flex; justify-content:space-between; font-size:10px; font-weight:700; color:#aaa; margin-top:14px; text-transform:uppercase;">
            <span>Network Status</span><span style="color:#4ADE80;">Total Coverage</span>
        </div>
        <div class="progress-bar-bg"><div class="progress-bar-fill"></div></div>
    </div>

    <!-- WEST REGION -->
    <div class="data-box" style="bottom: 45%; left: 2%;">
        <div class="data-box-title"><span style="color: #2ca02c;">■</span> WEST</div>
        <div class="data-box-row"><span>Branches:</span> <b>3</b></div>
        <div class="data-box-row"><span>Schools:</span> <b>83</b></div>
        <div class="data-box-row"><span>Students:</span> <b>115,500</b></div>
    </div>
    <div class="connecting-line" style="bottom: 49%; left: 12%; width: 140px;"></div>

    <!-- NORTH REGION -->
    <div class="data-box" style="top: 2%; left: 42%;">
        <div class="data-box-title"><span style="color: #1f77b4;">■</span> NORTH</div>
        <div class="data-box-row"><span>Branches:</span> <b>5</b></div>
        <div class="data-box-row"><span>Schools:</span> <b>124</b></div>
        <div class="data-box-row"><span>Students:</span> <b>172,200</b></div>
    </div>
    <div class="connecting-line vertical" style="top: 13%; left: 47%; height: 220px;"></div>

    <!-- EAST REGION -->
    <div class="data-box" style="top: 25%; right: 2%;">
        <div class="data-box-title"><span style="color: #ff7f0e;">■</span> EAST</div>
        <div class="data-box-row"><span>Branches:</span> <b>4</b></div>
        <div class="data-box-row"><span>Schools:</span> <b>47</b></div>
        <div class="data-box-row"><span>Students:</span> <b>64,500</b></div>
    </div>
    <div class="connecting-line" style="top: 31%; right: 12%; width: 140px;"></div>

    <!-- CENTRAL REGION -->
    <div class="data-box" style="bottom: 2%; left: 43%;">
        <div class="data-box-title"><span style="color: #d62728;">■</span> CENTRAL</div>
        <div class="data-box-row"><span>Branches:</span> <b>5</b></div>
        <div class="data-box-row"><span>Schools:</span> <b>83</b></div>
        <div class="data-box-row"><span>Students:</span> <b>115,500</b></div>
    </div>
    <div class="connecting-line vertical" style="bottom: 13%; left: 47.5%; height: 95px;"></div>
    """
    m.get_root().html.add_child(Element(dashboard_html))

    # Adds the final layer control toggle - Sets collapsed to True so it acts as a clean hover button
    folium.LayerControl(collapsed=True, position='topright').add_to(m)
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
