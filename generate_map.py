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

# Default 17 Acer Academy Branches (Fallback/Core Locations)
ACER_BRANCHES = [
    {"name": "Woodlands Branch", "lat": 1.4360, "lon": 103.7865},
    {"name": "Yishun Branch", "lat": 1.4294, "lon": 103.8350},
    {"name": "Sembawang Branch", "lat": 1.4491, "lon": 103.8201},
    {"name": "Mandai Branch", "lat": 1.4036, "lon": 103.7898},
    {"name": "Bukit Batok Branch", "lat": 1.3496, "lon": 103.7496},
    {"name": "Boon Lay Branch", "lat": 1.3385, "lon": 103.7058},
    {"name": "Jurong East Branch", "lat": 1.3331, "lon": 103.7423},
    {"name": "Queenstown Branch", "lat": 1.2942, "lon": 103.8061},
    {"name": "Bukit Merah Branch", "lat": 1.2819, "lon": 103.8185},
    {"name": "Telok Blangah Branch", "lat": 1.2730, "lon": 103.8090},
    {"name": "Orchard Branch", "lat": 1.3039, "lon": 103.8320},
    {"name": "River Valley Branch", "lat": 1.2931, "lon": 103.8355},
    {"name": "Marine Parade Branch", "lat": 1.3020, "lon": 103.9050},
    {"name": "Pasir Ris Branch", "lat": 1.3721, "lon": 103.9474},
    {"name": "Tampines Branch", "lat": 1.3526, "lon": 103.9447},
    {"name": "Simei Branch", "lat": 1.3431, "lon": 103.9533},
    {"name": "Hougang Branch", "lat": 1.3713, "lon": 103.8925}
]

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
    
    # Catch url/website first, then exclude them when searching for physical address
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
            
            # Micro-jitter (~150m scatter) to prevent overlapping dots in neighborhood hubs
            jitter_lat = float(val_lat) + random.uniform(-0.0015, 0.0015)
            jitter_lon = float(val_lon) + random.uniform(-0.0015, 0.0015)
            
            name = str(row[name_col]).strip() if name_col and pd.notna(row[name_col]) else "Unknown School"
            tier = str(row[tier_col]).strip() if tier_col and pd.notna(row[tier_col]) else ""
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
    # Initialize Map centered on Singapore with boundary locks
    m = folium.Map(
        location=[1.3521, 103.8198],
        zoom_start=12,
        min_zoom=11,
        max_zoom=18,
        tiles="CartoDB dark_matter",
        max_bounds=True,
        min_lat=1.15,
        max_lat=1.48,
        min_lon=103.58,
        max_lon=104.05
    )

    # Base Tile Options
    folium.TileLayer("CartoDB positron", name="Light Canvas").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Dark Streets (Default)").add_to(m)
    folium.TileLayer("CartoDB dark_matter", name="Executive Dark Canvas (Clean)").add_to(m)

    # Load Data
    schools = load_schools_from_csv(SCHOOL_DB_PATH)

    # Feature Feature Groups
    fg_branches = folium.FeatureGroup(name="Acer Academy Branches", show=True).add_to(m)
    fg_primary = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True).add_to(m)
    fg_secondary = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True).add_to(m)
    fg_jc = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True).add_to(m)
    fg_intl = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True).add_to(m)
    fg_heatmap = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False).add_to(m)
    fg_regions = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True).add_to(m)

    # 1. Add Acer Academy Branches (Custom Red 'A' Markers)
    for branch in ACER_BRANCHES:
        icon_html = """
        <div style="
            background-color: #ff2a2a;
            color: white;
            font-weight: 900;
            font-family: Arial, sans-serif;
            font-size: 14px;
            width: 28px;
            height: 28px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            border: 2px solid #ffffff;
            box-shadow: 0 0 10px rgba(255,42,42,0.8);
            cursor: pointer;">
            A
        </div>
        """
        folium.Marker(
            location=[branch["lat"], branch["lon"]],
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14)),
            tooltip=f"<b>{branch['name']}</b>"
        ).add_to(fg_branches)

    # 2. Add School Markers & Categorize by Level
    heat_data = []
    for s in schools:
        heat_data.append([s["lat"], s["lon"], 1.0])
        
        level_lower = s["level"].lower()
        if "primary" in level_lower:
            target_fg = fg_primary
            dot_color = "#38b6ff"
        elif "secondary" in level_lower:
            target_fg = fg_secondary
            dot_color = "#9d4edd"
        elif "college" in level_lower or "jc" in level_lower or "pre-u" in level_lower:
            target_fg = fg_jc
            dot_color = "#ffb703"
        else:
            target_fg = fg_intl
            dot_color = "#ff4d6d"

        # Display Tier Badge ONLY if it is not "Standard" or empty
        tier_badge = ""
        if s["tier"] and s["tier"].lower() != "standard":
            tier_badge = f"""
            <div style="background:#ffd700; color:#000; padding:2px 8px; border-radius:4px; 
                        font-size:11px; font-weight:bold; display:inline-block; margin-bottom:8px;">
                ★ TIER: {s['tier'].upper()}
            </div>
            """

        url_link = f"""<div style="margin-top:6px;"><a href="{s['url']}" target="_blank" 
                       style="color:#38b6ff; text-decoration:none; font-size:11px;">Visit Website ↗</a></div>""" if s["url"] else ""

        popup_html = f"""
        <div style="font-family: 'Segoe UI', Arial, sans-serif; min-width: 220px; padding: 4px;">
            <div style="font-size: 13px; font-weight: bold; color: {dot_color}; margin-bottom: 6px; text-transform: uppercase;">
                {s['name']}
            </div>
            {tier_badge}
            <div style="font-size: 11px; color: #ccc; margin-bottom: 4px;">
                <b>Level:</b> {s['level']} | <b>Region:</b> {s['region']}
            </div>
            <div style="font-size: 11px; color: #fff; background: #2a2a32; padding: 6px; border-radius: 4px;">
                📍 <b>Addr:</b> {s['address']}
            </div>
            {url_link}
        </div>
        """

        folium.CircleMarker(
            location=[s["lat"], s["lon"]],
            radius=6,
            color=dot_color,
            fill=True,
            fill_color=dot_color,
            fill_opacity=0.8,
            weight=1.5,
            popup=folium.Popup(popup_html, max_width=280)
        ).add_to(target_fg)

    # 3. Expansion Heatmap Layer (Vibrant Neon Settings)
    if heat_data:
        HeatMap(
            heat_data,
            radius=18,
            blur=12,
            min_opacity=0.4,
            gradient={0.2: '#0000ff', 0.4: '#00ffff', 0.6: '#00ff00', 0.8: '#ffff00', 1.0: '#ff0000'}
        ).add_to(fg_heatmap)

    # 4. Regional Boundaries (Choropleth Polygon Overlay)
    if os.path.exists(URA_REGIONS_PATH):
        try:
            with open(URA_REGIONS_PATH, "r") as f:
                geo_data = json.load(f)
            
            def style_function(feature):
                region_name = feature.get("properties", {}).get("name", "").lower()
                color_map = {
                    "north": "#1f77b4",
                    "west": "#2ca02c",
                    "central": "#d62728",
                    "east": "#ff7f0e",
                    "north-east": "#9467bd"
                }
                return {
                    "fillColor": color_map.get(region_name, "#555555"),
                    "color": "#ffffff",
                    "weight": 1.5,
                    "fillOpacity": 0.15
                }

            folium.GeoJson(
                geo_data,
                style_function=style_function,
                name="Regional Boundaries"
            ).add_to(fg_regions)
            print("[*] Successfully loaded regional boundary polygons.")
        except Exception as e:
            print(f"[!] Could not load GeoJSON: {e}")

    # ==========================================
    # 4. INJECT CUSTOM CSS & JS UI OVERLAYS
    # ==========================================
    map_root = m.get_root()

    custom_ui_html = f"""
    <style>
    /* 1. Leaflet Dark Theme Popup Override */
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {{
        background: #1e1e24 !important;
        color: #ffffff !important;
        border: 1px solid #444 !important;
        border-radius: 8px !important;
        box-shadow: 0 6px 18px rgba(0,0,0,0.7) !important;
    }}
    .leaflet-popup-close-button {{
        color: #aaaaaa !important;
    }}
    
    /* 2. Top-Right Acer Expansion Dashboard Box */
    .acer-dashboard {{
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 9999;
        background: rgba(20, 20, 25, 0.9);
        border: 1px solid #333;
        border-radius: 8px;
        padding: 14px 18px;
        width: 250px;
        font-family: 'Segoe UI', Arial, sans-serif;
        color: #ffffff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        backdrop-filter: blur(5px);
    }}
    .acer-dashboard h4 {{
        margin: 0 0 8px 0;
        font-size: 14px;
        letter-spacing: 1px;
        color: #ff2a2a;
        display: flex;
        align-items: center;
        gap: 6px;
    }}
    .acer-stat {{
        display: flex;
        justify-content: space-between;
        font-size: 12px;
        margin-bottom: 6px;
        color: #ddd;
    }}
    .acer-stat b {{
        color: #fff;
    }}
    .progress-bar-bg {{
        background: #333;
        height: 6px;
        border-radius: 3px;
        overflow: hidden;
        margin-top: 8px;
    }}
    .progress-bar-fill {{
        background: #ff2a2a;
        width: 65%;
        height: 100%;
    }}

    /* 3. Bottom-Right Directory Button */
    .directory-btn {{
        position: fixed;
        bottom: 25px;
        right: 20px;
        z-index: 9999;
        background: #ff2a2a;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 10px 16px;
        font-family: 'Segoe UI', Arial, sans-serif;
        font-weight: bold;
        font-size: 13px;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(255,42,42,0.4);
        transition: background 0.2s;
    }}
    .directory-btn:hover {{
        background: #d91c1c;
    }}

    /* 4. Fix Leaflet Menu Checkbox Alignment */
    .leaflet-control-layers-overlays label, .leaflet-control-layers-base label {{
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        color: #eee !important;
        font-size: 12px !important;
        font-family: 'Segoe UI', Arial, sans-serif !important;
        margin-bottom: 4px !important;
    }}
    .leaflet-control-layers {{
        background: rgba(20, 20, 25, 0.9) !important;
        border: 1px solid #333 !important;
        border-radius: 8px !important;
        padding: 10px !important;
    }}
    </style>

    <!-- Top-Right Dashboard Overlay -->
    <div class="acer-dashboard">
        <h4><span style="background:#ff2a2a; color:#fff; border-radius:3px; padding:1px 5px; font-size:11px;">A</span> ACER EXPANSION</h4>
        <div class="acer-stat"><span>Active Branches:</span> <b>{len(ACER_BRANCHES)}</b></div>
        <div class="acer-stat"><span>Tracked Schools:</span> <b>{len(schools)}</b></div>
        <div class="acer-stat"><span>Network Coverage:</span> <b>65%</b></div>
        <div class="progress-bar-bg"><div class="progress-bar-fill"></div></div>
    </div>

    <!-- Bottom-Right Directory Button -->
    <button class="directory-btn" onclick="alert('Directory view loading...')">📁 DIRECTORY</button>

    <!-- Synchronizer JS for Layer Menu -->
    <script>
    document.addEventListener("DOMContentLoaded", function() {{
        setTimeout(function() {{
            var layers = document.querySelectorAll('.leaflet-control-layers-selector');
            layers.forEach(function(item) {{
                item.addEventListener('change', function() {{
                    console.log('Layer toggled cleanly without DOM clash.');
                }});
            }});
        }}, 1000);
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
