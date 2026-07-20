import os
import csv
import json
import requests
import folium
from folium import plugins
from branca.element import Element

OUTPUT_MAP_PATH = "acer_expansion_map.html"

EXISTING_BRANCHES = {
    "Junction 9 (North)": (1.4325, 103.8408),
    "Admiralty Place (North)": (1.4404, 103.8003),
    "The Woodgrove (North)": (1.4311, 103.7844),
    "Vista Point (North)": (1.4315, 103.7937),
    "Canberra Plaza (North)": (1.4431, 103.8297),
    "Tampines West (East)": (1.3486, 103.9360),
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
    "Hong Kah (West)": (1.3496, 103.7210),
    "Dairy Farm (Franchise)": (1.3655125560760464, 103.77440746044067),
    "Beauty World (West)": (1.3425306367584264, 103.77657043601229)
}

def load_schools():
    """Strictly loads GPS from school_db.json. Cross-references CSV for extra text data."""
    schools = []
    csv_metadata = {}
    
    # 1. Harvest extra text info (Address & Website)
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

    # 2. BULLETPROOF JSON LOADER (Local or Network Fallback)
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

    # 3. Build the final strict array
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
    
    print(f"[+] Successfully loaded {len(schools)} schools.")
    return schools

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    
    # Initialize Map
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles=None)

    folium.TileLayer('CartoDB dark_matter', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    folium.TileLayer('OpenStreetMap', name='Standard Map', show=False).add_to(m)

    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    .leaflet-tooltip {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 14px !important; font-weight: 600 !important;
        padding: 8px 12px !important; background-color: rgba(20, 20, 20, 0.95) !important;
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
        padding: 22px 28px !important; font-family: 'Montserrat', sans-serif !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important; min-width: 250px !important;
    }
    .leaflet-control-layers-list::before {
        content: "Map Display Settings"; display: block; font-size: 15px; font-weight: 700; color: #00E5FF;
        text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px;
        border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 10px;
    }
    .leaflet-control-layers-base label, .leaflet-control-layers-overlays label {
        display: flex !important; align-items: center !important; margin: 14px 0 !important; cursor: pointer !important; font-weight: 500 !important; transition: color 0.2s !important;
    }
    .leaflet-control-layers-base label:hover, .leaflet-control-layers-overlays label:hover { color: #FFD700 !important; }
    .leaflet-control-layers-separator { border-top: 1px solid rgba(255,255,255,0.15) !important; margin: 18px 0 !important; }

    input[type="checkbox"].leaflet-control-layers-selector,
    input[type="radio"].leaflet-control-layers-selector {
        appearance: none; -webkit-appearance: none; width: 18px !important; height: 18px !important;
        border: 2px solid #888 !important; border-radius: 4px; margin-right: 12px !important; cursor: pointer !important;
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
    .region-label {
        font-family: 'Montserrat', sans-serif !important; font-size: 12px !important; text-transform: uppercase !important;
        letter-spacing: 2px !important; color: #ffffff !important; white-space: nowrap !important; pointer-events: none !important; 
        text-shadow: -1px -1px 3px #000, 1px -1px 3px #000, -1px 1px 3px #000, 1px 1px 3px #000, 0px 0px 15px rgba(0,0,0,0.8) !important;
        font-weight: 700 !important; transform: translate(-50%, -50%) !important;
    }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    print("[*] Plotting URA Regions...")
    ura_group = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True)
    
    ura_data = None
    if os.path.exists("ura_regions.json"):
        with open("ura_regions.json", "r") as f:
            ura_data = json.load(f)
    else:
        print("[!] Local ura_regions.json missing. Fetching from GitHub directly...")
        try:
            res = requests.get("https://raw.githubusercontent.com/itsray01/acerexpansion/main/ura_regions.json", timeout=10)
            if res.status_code == 200: ura_data = res.json()
        except Exception as e:
            print(f"[!] URA network fetch failed: {e}")

    def get_region_color(feature):
        # Scan the GeoJSON properties to identify the region and assign VIBRANT colors
        prop_str = str(feature.get('properties', {})).upper()
        
        if 'CENTRAL' in prop_str: return '#F43F5E' # Vibrant Rose/Red
        if 'WEST' in prop_str: return '#10B981' # Emerald Green
        if 'EAST' in prop_str and 'NORTH' not in prop_str: return '#F97316' # Vibrant Orange
        if 'NORTH' in prop_str: return '#0EA5E9' # Vibrant Sky Blue
        
        return '#333333' # Fallback

    if ura_data:
        folium.GeoJson(
            ura_data,
            style_function=lambda feature: {
                'fillColor': get_region_color(feature),
                'color': 'transparent', # NO WHITE LINES
                'weight': 0,
                'fillOpacity': 0.15, # Extremely light so it doesn't darken the map
                'interactive': False # CRITICAL: Let mouse clicks pass through to schools
            }
        ).add_to(ura_group)
    ura_group.add_to(m)

    print("[*] Plotting Expansion Heatmap...")
    heatmap_group = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False)
    heat_data = [[s['lat'], s['lon']] for s in schools]
    # max_zoom=13 prevents the red dots from washing out into blue when zooming in closely!
    plugins.HeatMap(heat_data, radius=45, blur=35, max_zoom=13).add_to(heatmap_group)
    heatmap_group.add_to(m)

    print(f"[*] Plotting {len(schools)} schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True)
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True)
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True)
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True)
    
    # Store exact hex colors for the region data boxes
    stats = {
        "NORTH": [0,0, '#0EA5E9'], 
        "EAST": [0,0, '#F97316'], 
        "WEST": [0,0, '#10B981'], 
        "CENTRAL": [0,0, '#F43F5E']
    }

    for school in schools:
        level = school.get("level", "").upper()
        # ABSOLUTELY NO RANDOM JITTER - STRICT EXACT GPS
        lat, lon = school["lat"], school["lon"]
        name, address, website = school["name"], school["address"], school["website"]
        
        # Simple clustering for the data boxes
        if lat > 1.41: stats["NORTH"][1] += 1
        elif lon > 103.89: stats["EAST"][1] += 1
        elif lon < 103.78: stats["WEST"][1] += 1
        else: stats["CENTRAL"][1] += 1
        
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
        
    primary_group.add_to(m)
    secondary_group.add_to(m)
    jc_group.add_to(m)
    intl_group.add_to(m)

    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Branches...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        if lat > 1.41: stats["NORTH"][0] += 1
        elif lon > 103.89: stats["EAST"][0] += 1
        elif lon < 103.78: stats["WEST"][0] += 1
        else: stats["CENTRAL"][0] += 1
        
        # PURE TRANSPARENT BACKGROUND FOR THE LOGO
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
        
        # Perfect Cyan rings
        folium.Circle(
            location=[lat, lon], radius=1500, color="#00C9FF", weight=2, fill_color="#00C9FF", fill_opacity=0.18
        ).add_to(branch_group)
    branch_group.add_to(m)

    sim_group = folium.FeatureGroup(name="Simulate Expansion (Click Map)", show=False)
    m.add_child(sim_group)
    
    sim_js = f"""
    <script>
    document.addEventListener("DOMContentLoaded", function() {{
        var map = null;
        for (var key in window) {{
            if (key.startsWith('map_')) {{ map = window[key]; break; }}
        }}
        if (map) {{
            var simGroup = {sim_group.get_name()};
            
            map.on('click', function(e) {{
                if (map.hasLayer(simGroup)) {{
                    simGroup.clearLayers();
                    
                    var marker = L.marker(e.latlng, {{
                        icon: L.divIcon({{
                            className: 'custom-div-icon',
                            html: "<div style='background-color: #FFD700; width: 14px; height: 14px; border-radius: 50%; border: 2px solid #fff; box-shadow: 0 0 10px #FFD700;'></div>",
                            iconSize: [14, 14],
                            iconAnchor: [7, 7]
                        }})
                    }}).addTo(simGroup);
                    
                    var circle = L.circle(e.latlng, {{
                        radius: 1500,
                        color: '#FFD700',
                        weight: 2,
                        fillColor: '#FFD700',
                        fillOpacity: 0.2
                    }}).addTo(simGroup);
                    
                    marker.bindPopup("<b style='color:#FFD700'>Simulated Branch</b><br>1.5km Radius").openPopup();
                }}
            }});
        }}
    }});
    </script>
    """
    m.get_root().html.add_child(Element(sim_js))

    data_box_group = folium.FeatureGroup(name="Regional Data Boxes", show=True)

    def create_box(region, b_count, s_count, region_color):
        students = s_count * 1250
        return """
        <div style="background: rgba(15,15,15,0.95); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); color: white; font-family: 'Montserrat', sans-serif; width: 160px; box-shadow: 0 8px 20px rgba(0,0,0,0.6); backdrop-filter: blur(8px);">
            <div style="font-size: 13px; font-weight: 800; margin-bottom: 10px; color: """ + region_color + """;">■ """ + region + """</div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Branches:</span><b style="color: #FBBF24;">""" + str(b_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Schools:</span><b style="color: #38BDF8;">""" + str(s_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #aaa;"><span>Students:</span><b style="color: #4ADE80;">""" + f"{students:,}" + """</b></div>
        </div>
        """

    # Format: ("REGION NAME", [Box Latitude, Box Longitude], [Target Latitude, Target Longitude])
    regions_setup = [
        ("NORTH", [1.55, 103.82], [1.44, 103.82]),    # Vertical (Same lon: 103.82) - Pushed into Johor
        ("EAST",  [1.35, 104.12], [1.35, 103.95]),    # Horizontal (Same lat: 1.35) - Pushed into Ocean
        ("WEST",  [1.364, 103.55], [1.364, 103.72]),  # Horizontal (Same lat: 1.364) - Pushed past Tuas
        ("CENTRAL",[1.18, 103.82], [1.28, 103.82])    # Vertical (Same lon: 103.82) - Pushed past Sentosa
    ]

    for reg_name, box_coord, map_coord in regions_setup:
        folium.PolyLine(
            locations=[box_coord, map_coord],
            color="#00E5FF", weight=2, dash_array="5, 10", opacity=0.6
        ).add_to(data_box_group)
        
        folium.Marker(
            location=box_coord,
            icon=folium.DivIcon(html=create_box(reg_name, stats[reg_name][0], stats[reg_name][1], stats[reg_name][2]), icon_size=(160, 100), icon_anchor=(80, 50))
        ).add_to(data_box_group)
        
    data_box_group.add_to(m)

    # Set Map Bounds to include the pushed-out boxes
    m.fit_bounds([[1.15, 103.55], [1.55, 104.12]])
    
    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    
    # Live Dark Mode JS Engine + Legend HTML (No dashboard!)
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
            <div style="background: transparent; width: 22px; height: 22px; border-radius: 5px; border: 1px solid white; margin-right: 14px; display: flex; justify-content: center; align-items: center; overflow: hidden; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%;">
            </div>
            <span class="legend-text" style="font-weight: 600; color: white;">Acer Academy</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #00C9FF; margin-right: 14px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <div id="legend-ring-inner" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div>
            </div>
            <span class="legend-text" style="color: white; font-weight: 500;">1.5km Radius Ring</span>
        </div>

        <div style="display: flex; align-items: center; margin-bottom: 18px; margin-top: 5px;">
            <div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #FFD700; margin-right: 14px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <div id="legend-ring-inner-sim" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div>
            </div>
            <span class="legend-text" style="color: white; font-weight: 500;">Simulated 1.5km Ring</span>
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
            map.on('baselayerchange', function(e) {
                var legend = document.getElementById('legend-box');
                var title = legend ? legend.querySelector('h4') : null;
                var innerRing = document.getElementById('legend-ring-inner');
                var innerRingSim = document.getElementById('legend-ring-inner-sim');
                var spans = legend ? legend.querySelectorAll('span.legend-text') : [];
                
                var isDark = (e.name === 'Dark Streets (Default)');

                if (isDark) {
                    if (legend) {
                        legend.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                        legend.style.borderColor = 'rgba(255,255,255,0.15)';
                        title.style.color = '#00E5FF';
                        title.style.borderBottom = '1px solid rgba(255,255,255,0.15)';
                        spans.forEach(s => s.style.color = 'white');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                        if (innerRingSim) innerRingSim.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                    }
                } else {
                    if (legend) {
                        legend.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                        legend.style.borderColor = '#ccc';
                        title.style.color = '#111';
                        title.style.borderBottom = '1px solid #ccc';
                        spans.forEach(s => s.style.color = '#333');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                        if (innerRingSim) innerRingSim.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                    }
                }
            });
        }
    });
    </script>
    '''
    m.get_root().html.add_child(Element(legend_html))
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
