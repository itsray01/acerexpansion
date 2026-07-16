import json
import os
import requests
import math
import folium
from folium import plugins
from folium import Element

# ==========================================
# 1. CONFIGURATION
# ==========================================
SCHOOL_DB_PATH = "school_db.json"
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
# 2. SPATIAL MATH ENGINE
# ==========================================
def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two GPS points in meters."""
    R = 6371000 # Radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def load_schools():
    if not os.path.exists(SCHOOL_DB_PATH):
        print(f"[!] Cannot find {SCHOOL_DB_PATH}. Run build_school_db.py first!")
        return []
    with open(SCHOOL_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

# ==========================================
# 3. MAP BUILDER
# ==========================================
def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    if not schools: return
    
    # Initialize the map with 'tiles=None' so we can explicitly order our base maps
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=13, tiles=None)
    
    # 1. Dark Streets (Default)
    folium.TileLayer('OpenStreetMap', name='Dark Streets (Default)', show=True).add_to(m)
    
    # 2. Light Canvas
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)

    # 3. Standard OpenStreetMap (Full original colors)
    folium.TileLayer('OpenStreetMap', name='Standard OpenStreetMap', show=False).add_to(m)
    
    # Inject Custom CSS
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
        /* Padding added to create a seamless hover bridge so the menu doesn't drop! */
        padding: 15px !important;
        margin-top: -15px !important;
        margin-right: -15px !important;
    }

    .leaflet-touch .leaflet-control-layers-toggle,
    .leaflet-retina .leaflet-control-layers-toggle,
    .leaflet-control-layers-toggle {
        margin-left: auto !important; /* Push icon to the right inside the new padding */
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
        min-width: 280px !important;
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
        z-index: 9999 !important; /* Force text on top of all circles/markers */
        font-family: 'Montserrat', sans-serif !important;
        font-size: 13px !important;
        text-transform: uppercase !important;
        letter-spacing: 3.5px !important;
        white-space: nowrap !important;
        pointer-events: none !important; 
        transform: translate(-50%, -50%) !important;
        transition: all 0.2s ease !important;
        /* Dynamic text/shadow colors handled by JS based on map layer */
    }
    
    /* ====================================================
       SLIDE-OUT DIRECTORY SIDEBAR & BACKDROP
       ==================================================== */
    #sidebar-backdrop {
        position: fixed;
        top: 0; left: 0; width: 100vw; height: 100vh;
        background: rgba(0,0,0,0.5);
        z-index: 99998;
        opacity: 0;
        pointer-events: none;
        transition: opacity 0.3s;
    }
    #sidebar-backdrop.open {
        opacity: 1;
        pointer-events: auto;
    }
    
    #directory-btn {
        position: fixed;
        bottom: 30px; /* Moved to bottom right to avoid overlap with layers menu */
        right: 20px;
        z-index: 9997;
        background-color: rgba(25, 25, 25, 0.85);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.2);
        color: white;
        padding: 12px 18px;
        border-radius: 8px;
        font-family: 'Montserrat', sans-serif;
        font-weight: 600;
        font-size: 14px;
        cursor: pointer;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        transition: all 0.3s;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    #directory-btn:hover { background-color: rgba(40,40,40,0.95); border-color: #00E5FF; color: #00E5FF; transform: translateY(-2px); }
    
    #side-panel {
        position: fixed;
        top: 0; right: -400px; /* Hidden off-screen by default */
        width: 320px; height: 100vh;
        background-color: rgba(20, 20, 20, 0.90);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border-left: 1px solid rgba(255,255,255,0.1);
        z-index: 99999;
        transition: right 0.4s cubic-bezier(0.25, 0.8, 0.25, 1);
        color: white;
        font-family: 'Montserrat', sans-serif;
        display: flex; flex-direction: column;
        box-shadow: -5px 0 30px rgba(0,0,0,0.6);
        overflow: hidden; /* Stop full-panel scrolling */
    }
    #side-panel.open { right: 0; }
    
    .panel-header {
        display: flex; justify-content: space-between; align-items: center;
        padding: 20px 25px; border-bottom: 1px solid rgba(255,255,255,0.1);
        flex-shrink: 0; /* Keep header pinned to top */
    }
    .panel-header h2 { margin: 0; font-size: 16px; color: #00E5FF; text-transform: uppercase; letter-spacing: 1px; font-weight: 700; }
    #close-panel { background: none; border: none; color: white; font-size: 28px; cursor: pointer; transition: color 0.2s; }
    #close-panel:hover { color: #FF3D00; }
    
    .panel-content { 
        padding: 20px 25px; 
        overflow-y: auto; /* Only content scrolls */
        flex-grow: 1; 
    }
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

    # Safely draw a subtle dashed border around the mainland of Singapore
    sg_border_url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/SGP.geo.json"
    try:
        print("[*] Fetching Singapore geographic boundaries...")
        res = requests.get(sg_border_url, timeout=10)
        if res.status_code == 200:
            folium.GeoJson(
                res.json(),
                name="Singapore Mainland Border",
                style_function=lambda feature: {
                    'fillColor': 'none',
                    'color': '#9E9E9E',
                    'weight': 2,
                    'dashArray': '6, 6'
                }
            ).add_to(m)
    except Exception as e:
        print(f"[!] Warning: Network error fetching borders ({e}). Skipping boundary layer.")

    # ==========================================
    # SPATIAL ANALYSIS: POTENTIAL EXPANSION
    # ==========================================
    # We will automatically calculate which schools are outside the 1.5km radius of ALL branches
    potential_expansion_coords = []
    schools_dir = {"PRIMARY": [], "SECONDARY": [], "JUNIOR COLLEGE": [], "INTERNATIONAL": []}

    print(f"[*] Plotting {len(schools)} schools & running spatial analysis...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)")
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)")
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)")
    
    for school in schools:
        level = school.get("level", "").upper()
        lat = school["lat"]
        lon = school["lon"]
        name = school["name"]
        
        # Spatial Check: Is this school within 1.5km of ANY branch?
        is_covered = False
        for b_name, (b_lat, b_lon) in EXISTING_BRANCHES.items():
            if haversine(lat, lon, b_lat, b_lon) <= 1500:
                is_covered = True
                break
        
        if not is_covered:
            potential_expansion_coords.append([lat, lon])
        
        # Categorize for the map pins AND the directory panel
        if "PRIMARY" in level:
            fill_color = "#38BDF8" # Sky Blue
            group = primary_group
            schools_dir["PRIMARY"].append(name)
        elif "SECONDARY" in level:
            fill_color = "#A78BFA" # Soft Violet
            group = secondary_group
            schools_dir["SECONDARY"].append(name)
        elif "JUNIOR COLLEGE" in level:
            fill_color = "#FBBF24" # Golden Amber
            group = jc_group
            schools_dir["JUNIOR COLLEGE"].append(name)
        elif "INTERNATIONAL" in level:
            fill_color = "#F472B6" # Rose Pink
            group = intl_group
            schools_dir["INTERNATIONAL"].append(name)
        else:
            continue # Skip "Other Institutes" entirely!
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=7, 
            popup=f"<b style='color: {fill_color}'>{name}</b><br>{level.title()}",
            tooltip=f"<span style='font-size: 14px;'>{name}</span>",
            color="white", # Crisp white outline
            weight=1,
            fill_color=fill_color,
            fill=True,
            fill_opacity=0.85
        ).add_to(group)
        
    primary_group.add_to(m)
    secondary_group.add_to(m)
    jc_group.add_to(m)
    intl_group.add_to(m)

    # ==========================================
    # INJECT AUTOMATED HEATMAP (NEON GRADIENT)
    # ==========================================
    # Instead of red/orange, we use a sleek Cyan -> Violet -> Pink gradient to match the modern UI
    print(f"[*] Generating Heatmap for {len(potential_expansion_coords)} Potential Expansion Targets...")
    heatmap_group = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False)
    
    plugins.HeatMap(
        potential_expansion_coords,
        name="Potential Expansion Zones",
        radius=25,
        blur=20,
        gradient={0.4: '#00C9FF', 0.65: '#A78BFA', 1.0: '#F472B6'}
    ).add_to(heatmap_group)
    
    heatmap_group.add_to(m)

    # ==========================================
    # INJECT INTERACTIVE SIMULATION LAYER
    # ==========================================
    print(f"[*] Injecting Interactive Branch Simulation Engine...")
    sim_group = folium.FeatureGroup(name="Simulate New Branch (Click Map)", show=False)
    sim_group.add_to(m)

    # ==========================================
    # PLOT ACER BRANCHES
    # ==========================================
    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & 1.5km Radius Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        gradient_style = (
            "background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); "
            "border-radius: 50%; width: 28px; height: 28px; display: flex; "
            "align-items: center; justify-content: center; color: white; "
            "font-size: 14px; box-shadow: 0 0 12px rgba(0,0,0,0.5); "
            "border: 2px solid white; overflow: hidden;"
        )
        logo_url = "https://i.imgur.com/YhyOq9V.png"
        icon_html = f'<div style="{gradient_style}"><img src="{logo_url}" style="width: 100%; object-fit: contain;"></div>'
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 16px; font-weight: bold; white-space: nowrap;'>★ {name}</span>",
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
        ).add_to(branch_group)
        
        folium.Circle(
            location=[lat, lon],
            radius=1500, # 1.5km in meters
            popup=f"1.5km Radius Ring for {name}",
            color="#00C9FF", # Premium Glowing Electric Cyan
            weight=2,
            fill_color="#00C9FF",
            fill_opacity=0.18
        ).add_to(branch_group)
    branch_group.add_to(m)

    # ==========================================
    # INJECT REGION WATERMARKS (Last so it floats above everything)
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
    
    # ==========================================
    # BUILD DYNAMIC DIRECTORY SIDEBAR HTML
    # ==========================================
    sidebar_html = """
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
    
    # Iterate dynamically through categories and lists
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
        // Toggle Sidebar Script with Backdrop clicking
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

    # Live Dark Mode JS Engine, Legend HTML & Simulation Interaction Logic
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

        <div style="display: flex; align-items: center; margin-bottom: 18px;">
            <div style="background: linear-gradient(90deg, #00C9FF, #A78BFA, #F472B6); width: 22px; height: 12px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.5); margin-right: 14px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">Expansion Heatmap</span>
        </div>

        <div style="display: flex; align-items: center; margin-bottom: 18px;">
            <div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #39FF14; margin-right: 14px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <div id="legend-ring-inner-sim" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div>
            </div>
            <span class="legend-text" style="color: white; font-weight: 500;">Simulated Zone (Click)</span>
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

            // ==========================================
            // SIMULATION CLICK ENGINE
            // ==========================================
            var simActive = false;
            var simLayer = null;

            map.on('overlayadd', function(e) {
                if (e.name === 'Simulate New Branch (Click Map)') {
                    simActive = true;
                    simLayer = e.layer;
                }
            });

            map.on('overlayremove', function(e) {
                if (e.name === 'Simulate New Branch (Click Map)') {
                    simActive = false;
                }
            });

            map.on('click', function(e) {
                if (!simActive || !simLayer) return;
                
                // Draw new simulated neon green radius ring
                var circle = L.circle(e.latlng, {
                    radius: 1500, // 1.5km
                    color: '#39FF14', // Neon Green
                    weight: 2.5,
                    fillColor: '#39FF14',
                    fillOpacity: 0.18,
                    interactive: true,
                    bubblingMouseEvents: false // Prevents the map click from firing when clicking the circle to remove it
                });
                
                circle.bindTooltip("<span style='font-size: 14px; font-weight: bold;'>Simulated Zone<br>👆 Click to remove</span>", {direction: 'top'});
                
                circle.on('click', function(ev) {
                    simLayer.removeLayer(circle); // Remove self on click
                });
                
                simLayer.addLayer(circle);
            });

            // ==========================================
            // BASE LAYER THEME MANAGER
            // ==========================================
            map.on('baselayerchange', function(e) {
                var legend = document.getElementById('legend-box');
                var sidePanel = document.getElementById('side-panel');
                var title = legend ? legend.querySelector('h4') : null;
                var innerRing = document.getElementById('legend-ring-inner');
                var innerRingSim = document.getElementById('legend-ring-inner-sim');
                var spans = legend ? legend.querySelectorAll('span.legend-text') : [];
                var regionLabels = document.querySelectorAll('.region-label');
                
                var isDark = (e.name === 'Dark Streets (Default)');

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
                        if (innerRingSim) innerRingSim.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
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
                        if (innerRingSim) innerRingSim.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
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
    
    # Add a Layer Control panel so you can toggle maps and school types on/off
    folium.LayerControl(position='topright').add_to(m)
    
    # Save the map to an HTML file
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
