import os
import json
import random
import pandas as pd
import folium
from folium.plugins import HeatMap
from folium import Element

# ==========================================
# 1. CONFIGURATION
# ==========================================
SCHOOL_DB_PATH = "All_Schools_Geocoded.csv"
URA_REGIONS_PATH = "ura_regions.json"
OUTPUT_MAP_PATH = "acer_expansion_map.html"

EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4325, 103.8408),
    "Admiralty Place (North)": (1.4404, 103.8003),
    "The Woodgrove (North)": (1.4311, 103.7844),
    "Vista Point (North)": (1.4315, 103.7937),
    "Canberra Plaza (North)": (1.4431, 103.8297),
    "Tampines West (East)": (1.3486, 103.9360),
    "Buangkok Square (East)": (1.3837, 103.8823),
    "Aljunied (East)": (1.3215, 103.8872),
    "Elias Mall (East)": (1.3773, 103.9424),
    "Dawson (Central)": (1.2941, 103.8099),
    "Depot Heights (Central)": (1.2809, 103.8086),
    "Tiong Bahru (Central)": (1.2861, 103.8285),
    "Cantonment (Central)": (1.2766, 103.8413),
    "Commonwealth (Central)": (1.3025, 103.7983),
    "Senja Heights (West)": (1.3853, 103.7629),
    "Greenridge (West)": (1.3856, 103.7663),
    "Hong Kah (West)": (1.3496, 103.7210)
}

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

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools_from_csv(SCHOOL_DB_PATH)
    
    # Force dark theme native maps
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
    
    # Layer control options
    folium.TileLayer('CartoDB dark_matter', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='Executive Dark Canvas (Clean)', show=False).add_to(m)

    fg_regions = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True).add_to(m)
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
                    "color": "transparent",  # Removes the jagged white border
                    "weight": 0,
                    "fillOpacity": 0.15
                }

            folium.GeoJson(
                geo_data,
                style_function=style_function,
                name="Regional Boundaries"
            ).add_to(fg_regions)
        except Exception as e:
            print(f"[!] Could not load GeoJSON: {e}")

    fg_heatmap = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False).add_to(m)
    heat_data = [[s["lat"], s["lon"], 1.0] for s in schools]
    if heat_data:
        HeatMap(
            heat_data,
            radius=35, # Massively expanded radius for ~3.0km
            blur=25,
            min_opacity=0.4,
            gradient={0.2: '#0000ff', 0.4: '#00ffff', 0.6: '#00ff00', 0.8: '#ffff00', 1.0: '#ff0000'}
        ).add_to(fg_heatmap)

    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True).add_to(m)
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True).add_to(m)
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True).add_to(m)
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True).add_to(m)

    for s in schools:
        level_lower = s["level"].lower()
        if "primary" in level_lower:
            target_fg = primary_group
            dot_color = "#38BDF8"
        elif "secondary" in level_lower:
            target_fg = secondary_group
            dot_color = "#A78BFA"
        elif "college" in level_lower or "jc" in level_lower or "pre-u" in level_lower:
            target_fg = jc_group
            dot_color = "#FBBF24"
        else:
            target_fg = intl_group
            dot_color = "#F472B6"

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
            color="white",
            fill=True,
            fill_color=dot_color,
            fill_opacity=0.85,
            weight=1,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"<span style='font-size: 14px;'>{s['name']}</span>"
        ).add_to(target_fg)

    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True).add_to(m)
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        logo_url = "https://i.imgur.com/YhyOq9V.png"
        icon_html = f'''
        <div style="
            width: 32px;
            height: 32px;
            border-radius: 8px;
            box-shadow: 0 4px 10px rgba(0,0,0,0.5);
            border: 2px solid #ffffff;
            cursor: pointer;
            overflow: hidden;
            background-color: transparent; /* Transparent background */
            display: flex;
            align-items: center;
            justify-content: center;
        ">
            <img src="{logo_url}" style="width: 100%; height: 100%; object-fit: cover;">
        </div>
        '''
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 16px; font-weight: bold; white-space: nowrap;'>★ {name}</span>",
            icon=folium.DivIcon(html=icon_html, icon_size=(32, 32), icon_anchor=(16, 16))
        ).add_to(branch_group)
        
        folium.Circle(
            location=[lat, lon],
            radius=1500,
            color="#00C9FF", # Premium Glowing Electric Cyan
            weight=2,
            fill_color="#00C9FF",
            fill_opacity=0.15
        ).add_to(branch_group)

    fg_data_boxes = folium.FeatureGroup(name="Regional Data Boxes", show=True).add_to(m)
    # Note: Lats/Lons are locked here to enforce perfectly straight lines
    infographic_boxes = [
        {"region": "WEST", "center": [1.3650, 103.7300], "box": [1.3650, 103.6300], "color": "#4ADE80", "b": 3, "s": 83, "st": "115,500"},
        {"region": "NORTH", "center": [1.4200, 103.8100], "box": [1.4650, 103.8100], "color": "#38BDF8", "b": 5, "s": 124, "st": "172,200"},
        {"region": "EAST", "center": [1.3550, 103.9400], "box": [1.3550, 104.0300], "color": "#FBBF24", "b": 4, "s": 47, "st": "64,500"},
        {"region": "CENTRAL", "center": [1.3100, 103.8400], "box": [1.2500, 103.8400], "color": "#F87171", "b": 5, "s": 83, "st": "115,500"}
    ]
    
    for b in infographic_boxes:
        folium.PolyLine(
            locations=[b["box"], b["center"]],
            color=b["color"],
            weight=2,
            dash_array="5, 5",
            opacity=0.8
        ).add_to(fg_data_boxes)

        html = f"""
        <div style="
            background: rgba(20, 20, 25, 0.95);
            border: 1px solid {b['color']};
            border-radius: 6px;
            padding: 10px;
            color: white;
            font-family: 'Segoe UI', Arial, sans-serif;
            width: 140px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        ">
            <div style="color: {b['color']}; font-weight: 900; font-size: 13px; letter-spacing: 1px; margin-bottom: 8px; border-bottom: 1px solid #444; padding-bottom: 4px;">
                ■ {b['region']}
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                <span style="color: #aaa;">Branches:</span> <b style="color: #fff;">{b['b']}</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px;">
                <span style="color: #aaa;">Schools:</span> <b style="color: #38BDF8;">{b['s']}</b>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 11px;">
                <span style="color: #aaa;">Students:</span> <b style="color: #4ADE80;">{b['st']}</b>
            </div>
        </div>
        """
        folium.Marker(
            location=b["box"],
            icon=folium.DivIcon(html=html, icon_size=(140, 90), icon_anchor=(70, 45))
        ).add_to(fg_data_boxes)

    region_group = folium.FeatureGroup(name="Town & Region Labels", show=True).add_to(m)
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

    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

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
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {
        background: #1e1e24 !important;
        color: #ffffff !important;
        border: 1px solid #444 !important;
        border-radius: 8px !important;
        box-shadow: 0 6px 18px rgba(0,0,0,0.7) !important;
    }
    .leaflet-popup-close-button { color: #aaaaaa !important; }

    /* Custom Leaflet Menu Checkboxes */
    .leaflet-control-layers {
        background: rgba(20, 20, 25, 0.9) !important;
        border: 1px solid #333 !important;
        border-radius: 8px !important;
        padding: 15px !important;
        color: white !important;
        font-family: 'Montserrat', sans-serif !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.6) !important;
        backdrop-filter: blur(10px) !important;
    }
    .leaflet-control-layers-list::before {
        content: "MAP DISPLAY SETTINGS";
        display: block; font-size: 14px; font-weight: 700; color: #00C9FF; 
        margin-bottom: 12px; border-bottom: 1px solid #444; padding-bottom: 8px;
    }
    .leaflet-control-layers-base label, .leaflet-control-layers-overlays label {
        display: flex !important; align-items: center !important; gap: 8px !important; margin: 8px 0 !important;
    }
    input[type="checkbox"].leaflet-control-layers-selector, input[type="radio"].leaflet-control-layers-selector {
        appearance: none; -webkit-appearance: none; width: 16px !important; height: 16px !important;
        border: 2px solid #888 !important; border-radius: 4px; cursor: pointer !important;
        position: relative; background: rgba(255,255,255,0.1); flex-shrink: 0;
    }
    input[type="radio"].leaflet-control-layers-selector { border-radius: 50%; }
    input[type="checkbox"].leaflet-control-layers-selector:checked, input[type="radio"].leaflet-control-layers-selector:checked {
        background: #00C9FF !important; border-color: #00C9FF !important;
    }
    .region-label {
        position: relative !important; z-index: 9999 !important; font-family: 'Montserrat', sans-serif !important;
        font-size: 13px !important; text-transform: uppercase !important; letter-spacing: 3.5px !important;
        white-space: nowrap !important; pointer-events: none !important; transform: translate(-50%, -50%) !important;
    }

    /* Acer Expansion Top Right Dashboard */
    .acer-dashboard {
        position: fixed; top: 20px; right: 20px; z-index: 9999;
        background: rgba(20, 20, 25, 0.95); border: 1px solid #333; border-radius: 8px;
        padding: 16px 20px; width: 260px; font-family: 'Montserrat', sans-serif; color: #ffffff;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5); backdrop-filter: blur(5px);
    }
    .acer-dashboard h4 { margin: 0 0 8px 0; font-size: 15px; font-weight: 800; display: flex; align-items: center; gap: 8px; }
    .acer-stat { font-size: 11px; color: #aaa; margin-top: 8px; line-height: 1.5; }
    .progress-bar-bg { background: #333; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 12px; }
    .progress-bar-fill { background: #00C9FF; width: 65%; height: 100%; }
    
    /* Directory Button */
    .directory-btn {
        position: fixed; bottom: 25px; right: 20px; z-index: 9997;
        background: rgba(25, 25, 25, 0.85); color: white; border: 1px solid rgba(255,255,255,0.2);
        border-radius: 8px; padding: 12px 18px; font-family: 'Montserrat', sans-serif; font-weight: 600;
        font-size: 14px; cursor: pointer; box-shadow: 0 4px 15px rgba(0,0,0,0.5); transition: all 0.3s;
    }
    .directory-btn:hover { background: rgba(40,40,40,0.95); border-color: #00E5FF; color: #00E5FF; }
    </style>

    <div class="acer-dashboard">
        <h4>
            <div style="background-color: transparent; border-radius: 6px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #fff;">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <span>ACER <span style="color:#ff3344;">EXPANSION</span></span>
        </h4>
        <div class="acer-stat">Analyzing <b style="color:#fff;">{len(schools)}</b> educational zones across <b style="color:#fff;">{len(EXISTING_BRANCHES)}</b> active branches.</div>
        <div style="display:flex; justify-content:space-between; font-size:10px; font-weight:700; color:#aaa; margin-top:14px; text-transform:uppercase;">
            <span>Network Status</span><span style="color:#4ADE80;">Total Coverage</span>
        </div>
        <div class="progress-bar-bg"><div class="progress-bar-fill"></div></div>
    </div>
    
    <button class="directory-btn" onclick="alert('Directory view loading...')">📁 DIRECTORY</button>
    
    <script>
    document.addEventListener("DOMContentLoaded", function() {
        var map = null;
        for (var key in window) {
            if (key.startsWith('map_')) { map = window[key]; break; }
        }
        if (map) {
            // Apply default dark text shadows to labels
            document.querySelectorAll('.region-label').forEach(lbl => {
                lbl.style.color = '#ffffff';
                lbl.style.textShadow = '-1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8)';
                lbl.style.fontWeight = '700';
            });

            map.on('baselayerchange', function(e) {
                var isDark = e.name.includes('Dark');
                var regionLabels = document.querySelectorAll('.region-label');
                var controlPanel = document.querySelector('.leaflet-control-layers');
                
                if (isDark) {
                    if (controlPanel) {
                        controlPanel.style.background = 'rgba(20, 20, 25, 0.9)';
                        controlPanel.style.color = 'white';
                    }
                    regionLabels.forEach(lbl => {
                        lbl.style.color = '#ffffff';
                        lbl.style.textShadow = '-1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8)';
                        lbl.style.fontWeight = '700';
                    });
                } else {
                    if (controlPanel) {
                        controlPanel.style.background = 'rgba(255, 255, 255, 0.95)';
                        controlPanel.style.color = '#111';
                    }
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
    """
    m.get_root().html.add_child(Element(custom_css))

    folium.LayerControl(collapsed=False, position='topright').add_to(m)
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
