import os
import json
import math
import random
import pandas as pd
import folium
from folium.plugins import HeatMap

# ==========================================
# 1. CONFIGURATION & CONSTANTS
# ==========================================
SCHOOL_DB_PATH = "All_Schools_Geocoded.csv"
URA_REGIONS_PATH = "ura_regions.json"
OUTPUT_MAP = "singapore_schools_map.html"

# Default 17 Acer Academy Branches
ACER_BRANCHES = [
    {"name": "Woodlands (North)", "lat": 1.4360, "lon": 103.7865},
    {"name": "Yishun (North)", "lat": 1.4294, "lon": 103.8350},
    {"name": "Sembawang (North)", "lat": 1.4491, "lon": 103.8201},
    {"name": "Mandai (North)", "lat": 1.4036, "lon": 103.7898},
    {"name": "Bukit Batok (West)", "lat": 1.3496, "lon": 103.7496},
    {"name": "Boon Lay (West)", "lat": 1.3385, "lon": 103.7058},
    {"name": "Jurong East (West)", "lat": 1.3331, "lon": 103.7423},
    {"name": "Queenstown (Central)", "lat": 1.2942, "lon": 103.8061},
    {"name": "Bukit Merah (Central)", "lat": 1.2819, "lon": 103.8185},
    {"name": "Telok Blangah (Central)", "lat": 1.2730, "lon": 103.8090},
    {"name": "Orchard (Central)", "lat": 1.3039, "lon": 103.8320},
    {"name": "River Valley (Central)", "lat": 1.2931, "lon": 103.8355},
    {"name": "Marine Parade (East)", "lat": 1.3020, "lon": 103.9050},
    {"name": "Pasir Ris (East)", "lat": 1.3721, "lon": 103.9474},
    {"name": "Tampines (East)", "lat": 1.3526, "lon": 103.9447},
    {"name": "Simei (East)", "lat": 1.3431, "lon": 103.9533},
    {"name": "Hougang (East)", "lat": 1.3713, "lon": 103.8925}
]

# Town locations for the map labels
REGIONS_TOWNS = {
    "Punggol": (1.4050, 103.9020), "Sengkang": (1.3916, 103.8954), "Tampines": (1.3524, 103.9443),
    "Bedok": (1.3236, 103.9273), "Pasir Ris": (1.3721, 103.9474), "Jurong West": (1.3396, 103.7067),
    "Jurong East": (1.3329, 103.7436), "Clementi": (1.3162, 103.7649), "Bukit Batok": (1.3491, 103.7496),
    "Bukit Panjang": (1.3780, 103.7629), "Choa Chu Kang": (1.3840, 103.7470), "Woodlands": (1.4360, 103.7860),
    "Yishun": (1.4304, 103.8354), "Ang Mo Kio": (1.3691, 103.8454), "Bishan": (1.3526, 103.8352),
    "Toa Payoh": (1.3343, 103.8563), "Hougang": (1.3712, 103.8924), "Serangoon": (1.3554, 103.8679),
    "Bukit Timah": (1.3294, 103.8021), "Queenstown": (1.2942, 103.8062), "Bukit Merah": (1.2819, 103.8239),
    "Kallang": (1.3113, 103.8714), "Sembawang": (1.4491, 103.8185), "Novena": (1.3204, 103.8434), 
    "Marine Parade": (1.3020, 103.9046), "Tengah": (1.3700, 103.7000), "Changi": (1.3450, 103.9832), 
    "Simei": (1.3429, 103.9531), "MacPherson": (1.3262, 103.8887), "Seletar": (1.4098, 103.8750), 
    "Pioneer": (1.3184, 103.6934), "Boon Lay": (1.3385, 103.7058), "Tuas": (1.3294, 103.6397), 
    "West Coast": (1.3030, 103.7661), "Telok Blangah": (1.2741, 103.8159), "Sentosa": (1.2494, 103.8303), 
    "Central Area": (1.2789, 103.8536), "Orchard": (1.3048, 103.8318), "Newton": (1.3129, 103.8385), 
    "River Valley": (1.2974, 103.8340), "Balestier": (1.3261, 103.8475), "Mandai": (1.4241, 103.8052), 
    "Sungei Kadut": (1.4137, 103.7547), "Lim Chu Kang": (1.4342, 103.7149), "Marina Bay": (1.2842, 103.8535)
}

# ==========================================
# 2. SMART DATA LOADER
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
        print(f"[!] Warning: {filepath} not found. Skipping school loading.")
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
    
    # Catch url/website first, then strictly exclude them when searching for physical address
    url_col = get_col(cols, ["url", "web", "http", "link", "website"])
    addr_col = get_col(cols, ["address", "street", "addr", "location"], exclude_keywords=["url", "web", "http", "link", "website"])
    region_col = get_col(cols, ["region", "zone", "area", "sector"])

    if not lat_col or not lon_col:
        print("[!] Error: Could not detect Latitude/Longitude columns in CSV.")
        return []

    schools = []
    for idx, row in df.iterrows():
        try:
            val_lat = str(row[lat_col]).strip()
            val_lon = str(row[lon_col]).strip()
            if not val_lat or not val_lon or val_lat.lower() in ['nan', ''] or val_lon.lower() in ['nan', '']:
                continue
            
            # Micro-jitter (~150m scatter) to prevent perfectly overlapping dots
            jitter_lat = float(val_lat) + random.uniform(-0.0015, 0.0015)
            jitter_lon = float(val_lon) + random.uniform(-0.0015, 0.0015)
            
            name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Unknown School"
            tier = str(row[tier_col]).strip() if tier_col and pd.notna(row[tier_col]) else "Standard"
            level = str(row[level_col]).strip() if level_col and pd.notna(row[level_col]) else "General"
            addr = str(row[addr_col]).strip() if addr_col and pd.notna(row[addr_col]) else "Address unavailable"
            url = str(row[url_col]).strip() if url_col and pd.notna(row[url_col]) else ""
            region = str(row[region_col]).strip() if region_col and pd.notna(row[region_col]) else "Singapore"

            schools.append({
                "name": name,
                "lat": jitter_lat,
                "lon": jitter_lon,
                "tier": tier,
                "level": level,
                "address": addr,
                "url": url,
                "region": region
            })
        except ValueError:
            continue
            
    print(f"[*] Successfully loaded and geocoded {len(schools)} schools.")
    return schools

# ==========================================
# 3. MAP GENERATION & LAYERS SETUP
# ==========================================
def generate_map():
    print("[*] Booting up Master Infographic & Interactive Map Engine...")
    
    # Initialize Map centered on Singapore
    m = folium.Map(
        location=[1.3521, 103.8198],
        zoom_start=12,
        min_zoom=11,
        max_zoom=18,
        tiles=None, # Disable default tiles to use pure CartoDB Dark
        max_bounds=True,
        min_lat=1.15,
        max_lat=1.48,
        min_lon=103.58,
        max_lon=104.05,
        control_scale=True
    )

    # Base Tile Options (Added in specific order)
    folium.TileLayer("CartoDB dark_matter", name="Dark Streets (Default)").add_to(m)
    folium.TileLayer("CartoDB positron", name="Light Canvas").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Executive Dark Canvas (Clean)").add_to(m)

    # Load Data
    schools = load_schools_from_csv(SCHOOL_DB_PATH)

    # Feature Groups for toggling
    fg_regions = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True).add_to(m)
    fg_primary = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True).add_to(m)
    fg_secondary = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True).add_to(m)
    fg_jc = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True).add_to(m)
    fg_intl = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True).add_to(m)
    fg_heatmap = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False).add_to(m)
    fg_labels = folium.FeatureGroup(name="Town & Region Labels", show=True).add_to(m)
    fg_branches = folium.FeatureGroup(name="Acer Academy Branches", show=True).add_to(m)

    # 1. Regional Boundaries (Choropleth)
    if os.path.exists(URA_REGIONS_PATH):
        try:
            with open(URA_REGIONS_PATH, "r") as f:
                geo_data = json.load(f)
            
            def style_function(feature):
                region_name = feature.get("properties", {}).get("REGION_N", "").upper()
                if 'NORTH-EAST' in region_name or 'NORTH' in region_name: color = '#2b5c8f' # Deep Blue
                elif 'WEST' in region_name: color = '#1a5c38' # Deep Green
                elif 'EAST' in region_name: color = '#994d00' # Deep Orange/Brown
                else: color = '#8f1a26' # Deep Red (Central)
                
                return {
                    "fillColor": color,
                    "color": "#ffffff",
                    "weight": 1.2,
                    "fillOpacity": 0.35 # Match the screenshot's distinct tint
                }

            folium.GeoJson(
                geo_data,
                style_function=style_function,
                name="Regional Boundaries"
            ).add_to(fg_regions)
            print("[*] Successfully loaded regional boundary polygons.")
        except Exception as e:
            print(f"[!] Could not load GeoJSON: {e}")

    # 2. Add Acer Academy Branches (Custom Red 'A' Markers with Radius)
    for branch in ACER_BRANCHES:
        # The exact Red 'A' logo styling from the screenshot
        icon_html = """
        <div style="
            background-color: #ff3344;
            color: white;
            font-weight: 900;
            font-family: 'Montserrat', Arial, sans-serif;
            font-size: 16px;
            width: 32px;
            height: 32px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #ffffff;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            cursor: pointer;">
            A
        </div>
        """
        folium.Marker(
            location=[branch["lat"], branch["lon"]],
            icon=folium.DivIcon(html=icon_html, icon_size=(32, 32), icon_anchor=(16, 16)),
            tooltip=f"<b style='font-family: Arial;'>{branch['name']}</b>"
        ).add_to(fg_branches)

        # 1.5km Catchment radius circle
        folium.Circle(
            location=[branch["lat"], branch["lon"]],
            radius=1500,
            color='#ff3344',
            fill=True,
            fill_color='#ff3344',
            fill_opacity=0.1,
            weight=1.5
        ).add_to(fg_branches)

    # 3. Add School Markers & Categorize by Level
    heat_data = []
    for s in schools:
        heat_data.append([s["lat"], s["lon"], 1.0])
        
        level_lower = s["level"].lower()
        if "primary" in level_lower:
            target_fg = fg_primary
            dot_color = "#38b6ff" # Sky Blue
        elif "secondary" in level_lower:
            target_fg = fg_secondary
            dot_color = "#a78bfa" # Violet
        elif "college" in level_lower or "jc" in level_lower or "pre-u" in level_lower or "mixed" in level_lower:
            target_fg = fg_jc
            dot_color = "#fbbf24" # Amber
        else:
            target_fg = fg_intl
            dot_color = "#f472b6" # Rose Pink

        # Display Tier Badge ONLY if it is not "Standard" or missing
        tier_badge = ""
        if s["tier"] and s["tier"].lower() not in ["standard", "na", "n/a", ""]:
            tier_badge = f"""
            <div style="background: rgba(255, 215, 0, 0.1); border: 1px solid #FFD700; color: #FFD700; padding: 4px 8px; border-radius: 4px; 
                        font-size: 11px; font-weight: 700; display: inline-block; margin-bottom: 10px;">
                ★ TIER: {s['tier'].upper()}
            </div>
            """

        # Link strictly separated from address
        url_link = f"""<div style="margin-top: 8px;"><a href="{s['url']}" target="_blank" 
                       style="color: #38bdf8; text-decoration: underline; font-weight: 600; font-size: 11px;">Visit Website ↗</a></div>""" if s["url"] else ""

        # Executive Dark Popup HTML
        popup_html = f"""
        <div style="font-family: 'Montserrat', Arial, sans-serif; min-width: 240px; padding: 4px;">
            <div style="font-size: 14px; font-weight: 800; color: {dot_color}; margin-bottom: 6px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">
                {s['name']}
            </div>
            {tier_badge}
            <div style="font-size: 11px; color: #cccccc; line-height: 1.6;">
                <b style="color: #ffffff;">Level:</b> {s['level'].title()}<br>
                <b style="color: #ffffff;">Region:</b> {s['region'].title()}<br>
            </div>
            <div style="font-size: 11px; color: #ffffff; background: rgba(0,0,0,0.3); padding: 6px; border-radius: 4px; margin-top: 6px; border-left: 3px solid {dot_color};">
                📍 <b>Addr:</b> {s['address']}
            </div>
            {url_link}
        </div>
        """

        # Clean dots with white borders per the screenshot
        folium.CircleMarker(
            location=[s["lat"], s["lon"]],
            radius=5,
            color="#ffffff",
            weight=1,
            fill=True,
            fill_color=dot_color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(target_fg)

    # 4. Expansion Heatmap Layer (Vibrant Neon Settings)
    if heat_data:
        HeatMap(
            heat_data,
            name="Expansion Heatmap (Untapped)",
            radius=20, # Boosted for vibrancy with jitter
            blur=15,
            min_opacity=0.4,
            gradient={0.2: '#00c9ff', 0.5: '#a78bfa', 0.8: '#f472b6', 1.0: '#ffd700'}
        ).add_to(fg_heatmap)

    # 5. Town & Region Labels
    for town, (t_lat, t_lon) in REGIONS_TOWNS.items():
        folium.Marker(
            location=[t_lat, t_lon],
            icon=folium.DivIcon(
                html=f'<div style="font-family:\'Montserrat\',sans-serif; font-weight:800; font-size:10px; color:#ffffff; text-shadow:0px 0px 4px #000000, 0px 0px 8px rgba(0,0,0,0.8); text-transform:uppercase; letter-spacing:1px; white-space:nowrap;">{town.upper()}</div>',
                icon_size=(100, 20),
                icon_anchor=(50, 10)
            )
        ).add_to(fg_labels)

    # ==========================================
    # 5. INJECT CUSTOM CSS & JS UI OVERLAYS
    # ==========================================
    map_root = m.get_root()
    total_schools = len(schools)
    total_branches = len(ACER_BRANCHES)

    custom_ui_html = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800;900&display=swap');
    
    /* 1. Force Leaflet Popups to be Dark Theme */
    .leaflet-popup-content-wrapper {{
        background: rgba(20, 20, 24, 0.95) !important;
        border: 1px solid #333 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.7) !important;
        backdrop-filter: blur(8px);
    }}
    .leaflet-popup-tip {{
        background: rgba(20, 20, 24, 0.95) !important;
        border-top: 1px solid #333 !important;
        border-left: 1px solid #333 !important;
    }}
    .leaflet-popup-close-button {{ color: #FFFFFF !important; }}

    /* 2. Top-Right ACER EXPANSION Dashboard */
    .acer-dashboard {{
        position: absolute;
        top: 20px;
        right: 20px;
        z-index: 1000;
        background: rgba(15, 15, 18, 0.95);
        border: 1px solid #333;
        border-radius: 12px;
        padding: 16px;
        width: 260px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.6);
        backdrop-filter: blur(8px);
        font-family: 'Montserrat', sans-serif;
        pointer-events: none; /* Let clicks pass through to map if needed */
    }}
    
    /* 3. Right-Side MAP DISPLAY SETTINGS Menu */
    /* Push Leaflet controls down so they sit perfectly below the Acer Dashboard */
    .leaflet-top.leaflet-right .leaflet-control-layers {{
        margin-top: 140px !important; 
        background: rgba(15, 15, 18, 0.95) !important;
        border: 1px solid #333 !important;
        border-radius: 12px !important;
        padding: 16px !important;
        box-shadow: 0 8px 32px rgba(0,0,0,0.6) !important;
        backdrop-filter: blur(8px);
        font-family: 'Montserrat', sans-serif !important;
    }}
    .leaflet-control-layers-list::before {{
        content: "MAP DISPLAY SETTINGS";
        display: block;
        color: #38BDF8;
        font-weight: 800;
        font-size: 11px;
        letter-spacing: 1px;
        margin-bottom: 12px;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        padding-bottom: 8px;
    }}
    /* Flex alignment fix for checkboxes/radios */
    .leaflet-control-layers-overlays label div, .leaflet-control-layers-base label div {{
        display: flex;
        align-items: center;
        gap: 8px;
        color: #E2E8F0 !important;
        font-size: 11px !important;
        font-weight: 600 !important;
        margin-bottom: 6px !important;
    }}
    .leaflet-control-layers-overlays label span, .leaflet-control-layers-base label span {{
        line-height: 1.2;
    }}
    input[type="radio"], input[type="checkbox"] {{
        accent-color: #38BDF8 !important; 
        margin: 0 !important;
        width: 14px;
        height: 14px;
        cursor: pointer;
        flex-shrink: 0;
    }}
    .leaflet-control-layers-separator {{
        border-top: 1px solid rgba(255,255,255,0.1) !important;
        margin: 12px 0 !important;
    }}
    </style>

    <!-- Top-Right Acer Dashboard Injection -->
    <div id="acer-dashboard" class="acer-dashboard">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 12px;">
            <div style="background: #ff3344; width: 36px; height: 36px; border-radius: 8px; border: 2px solid #FFF; display: flex; align-items: center; justify-content: center; color: #FFF; font-weight: 900; font-size: 18px; box-shadow: 0 0 15px rgba(255,51,68,0.8);">A</div>
            <div style="line-height: 1.1;">
                <div style="color: #FFF; font-weight: 900; font-size: 18px; letter-spacing: 1px;">ACER</div>
                <div style="color: #ff3344; font-weight: 800; font-size: 11px; letter-spacing: 2px;">EXPANSION</div>
            </div>
        </div>
        <div style="color: #A0AEC0; font-size: 11px; line-height: 1.5; margin-bottom: 16px;">
            Analyzing <b style="color: #FFF;">{total_schools}</b> educational zones across <b style="color: #FFF;">{total_branches}</b> active branches.
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

    <!-- Recursive JS Synchronizer to prevent Leaflet Menu breaking -->
    <script>
    document.addEventListener('DOMContentLoaded', function() {{
        var map = null;
        for (var key in window) {{
            if (key.startsWith('map_') && window[key] instanceof L.Map) {{
                map = window[key];
                break;
            }}
        }}
        
        if (map) {{
            function syncLayers() {{
                var isExecClean = document.body.classList.contains('exec-mode-active');
                var inputs = document.querySelectorAll('.leaflet-control-layers-selector');
                var clicked = false;

                for(var i = 0; i < inputs.length; i++) {{
                    var cb = inputs[i];
                    var span = cb.nextElementSibling;
                    if(!span && cb.parentElement) span = cb.parentElement.querySelector('span');
                    if(!span) continue;

                    var label = span.textContent.trim();
                    var shouldBeChecked = cb.checked;

                    if (isExecClean) {{
                        if (label.includes('Schools') || label.includes('Heatmap')) {{
                            shouldBeChecked = false;
                        }} else if (label.includes('Branches') || label.includes('Choropleth') || label.includes('Town')) {{
                            shouldBeChecked = true;
                        }}
                    }} else {{
                        if (label.includes('Schools') || label.includes('Choropleth') || label.includes('Branches') || label.includes('Town')) {{
                            shouldBeChecked = true;
                        }}
                    }}

                    if (cb.checked !== shouldBeChecked) {{
                        cb.click();
                        clicked = true;
                        break; // Click one, let Leaflet rebuild, then loop again
                    }}
                }}
                if (clicked) {{
                    setTimeout(syncLayers, 50);
                }}
            }}

            map.on('baselayerchange', function(e) {{
                if (e.name === 'Executive Dark Canvas (Clean)') {{
                    document.body.classList.add('exec-mode-active');
                }} else {{
                    document.body.classList.remove('exec-mode-active');
                }}
                setTimeout(syncLayers, 50);
            }});
        }}
    }});
    </script>
    """
    map_root.html.add_child(folium.Element(custom_ui_html))

    # Add standard layer control menu
    folium.LayerControl(collapsed=False).add_to(m)

    # Save Output
    m.save(OUTPUT_MAP)
    print(f"[*] Map successfully generated and saved to: {OUTPUT_MAP}")

if __name__ == "__main__":
    generate_map()
