import os
import csv
import json
import random
import folium
from folium import plugins
from branca.element import Element

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
    """Merges exact GPS from JSON with rich metadata from CSV."""
    schools = []
    csv_metadata = {}
    
    # 1. Harvest rich data (Addresses & URLs) from the CSV first
    csv_file = "Generalinformationofschools.csv" if os.path.exists("Generalinformationofschools.csv") else "All_Schools_Geocoded.csv"
    if os.path.exists(csv_file):
        print(f"[*] Harvesting addresses & websites from {csv_file}...")
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
    else:
        print(f"[!] Warning: Neither Generalinformationofschools.csv nor All_Schools_Geocoded.csv found. Popups will lack rich text.")

    # 2. Strictly load positions from the highly-accurate JSON file
    if os.path.exists("school_db.json"):
        print("[*] Found school_db.json! Loading exact GPS coordinates...")
        with open("school_db.json", 'r', encoding='utf-8') as f:
            json_schools = json.load(f)
            for item in json_schools:
                name = item.get("name", "").strip()
                lower_name = name.lower()
                
                if "lat" in item and "lon" in item:
                    # Cross-reference with CSV metadata
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
        print(f"[+] Successfully merged {len(schools)} schools with precise GPS & CSV metadata.")
        return schools
        
    print("[!] CRITICAL: school_db.json not found! Cannot map schools accurately.")
    return []

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    if not schools: 
        print("[!] No schools loaded. Terminating map generation.")
        return
    
    # Initialize without tiles so we can control the Layer Menu options
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles=None)

    # 1. Base Maps
    folium.TileLayer('CartoDB dark_matter', name='Dark Streets (Default)', show=True).add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    folium.TileLayer('CartoDB dark_matter', name='Executive Dark Canvas (Clean)', show=False).add_to(m)

    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700;800&display=swap');

    /* Tooltip & Popup Styling */
    .leaflet-tooltip {
        font-family: 'Montserrat', sans-serif !important;
        font-size: 14px !important; font-weight: 600 !important;
        padding: 8px 12px !important; background-color: rgba(20, 20, 20, 0.95) !important;
        color: white !important; border: 1px solid #888 !important; border-radius: 8px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    }
    .leaflet-popup-content-wrapper, .leaflet-popup-tip {
        background: rgba(20, 20, 20, 0.95) !important;
        color: #fff !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        box-shadow: 0 10px 25px rgba(0,0,0,0.5) !important;
        border-radius: 12px !important;
    }
    .leaflet-popup-content { font-family: 'Montserrat', sans-serif !important; margin: 15px !important; }

    /* ====================================================
       OVERHAUL: CUSTOM BRANDED TRANSLUCENT LAYERS MENU
       ==================================================== */
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
        margin-top: 5px !important;
        background: rgba(20, 20, 20, 0.90) !important;
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
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    print("[*] Plotting URA Regions...")
    if os.path.exists("ura_regions.json"):
        try:
            folium.GeoJson(
                "ura_regions.json",
                name="Regional Boundaries (Choropleth)",
                style_function=lambda feature: {
                    'fillColor': feature['properties'].get('fill', '#333333'),
                    'color': 'transparent', 
                    'weight': 0,
                    'fillOpacity': 0.35,
                    'interactive': False # CRITICAL FIX: Allows clicking schools underneath!
                }
            ).add_to(m)
            print("[+] URA boundaries loaded successfully.")
        except Exception as e:
            print(f"[!] Failed to parse ura_regions.json: {e}")
    else:
        print("[!] ura_regions.json missing from repository. Skipping choropleth.")

    print("[*] Plotting Expansion Heatmap...")
    heat_data = [[s['lat'], s['lon']] for s in schools if 'lat' in s and 'lon' in s]
    plugins.HeatMap(heat_data, name="Expansion Heatmap (Untapped)", radius=45, blur=35, show=False).add_to(m)

    print(f"[*] Plotting {len(schools)} schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)")
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)")
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)")
    
    stats = {"NORTH": [0,0], "EAST": [0,0], "WEST": [0,0], "CENTRAL": [0,0]}

    for school in schools:
        level = school.get("level", "").upper()
        # Micro-jitter to prevent stacking
        lat = school["lat"] + random.uniform(-0.0008, 0.0008)
        lon = school["lon"] + random.uniform(-0.0008, 0.0008)
        name = school["name"]
        address = school["address"]
        website = school["website"]
        
        # Region Tracking
        if lat > 1.41: stats["NORTH"][1] += 1
        elif lon > 103.89: stats["EAST"][1] += 1
        elif lon < 103.78: stats["WEST"][1] += 1
        else: stats["CENTRAL"][1] += 1
        
        if "PRIMARY" in level: fill_color, group = "#38BDF8", primary_group
        elif "SECONDARY" in level: fill_color, group = "#A78BFA", secondary_group
        elif "JUNIOR COLLEGE" in level: fill_color, group = "#FBBF24", jc_group
        elif "INTERNATIONAL" in level: fill_color, group = "#F472B6", intl_group
        else: continue
            
        # Safely escape names for HTML to prevent popup JS breaks
        safe_name = name.replace("'", "&#39;")
        
        btn_html = f"<a href='{website}' target='_blank' style='display: inline-block; background: #00E5FF; color: #000; padding: 6px 12px; border-radius: 6px; font-size: 11px; font-weight: 700; text-decoration: none; margin-top: 5px;'>View Website &rarr;</a>" if website else ""
        popup_html = f"""
        <div style="min-width: 200px;">
            <b style="color: {fill_color}; font-size: 15px;">{safe_name}</b><br>
            <div style="font-size: 11px; color: #aaa; text-transform: uppercase; margin-bottom: 8px; font-weight: 600;">{level.title()}</div>
            <div style="font-size: 12px; color: #fff; line-height: 1.4; margin-bottom: 8px;">
                &#128205; {address}
            </div>
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
    branch_group.add_to(m)

    def create_box(region, b_count, s_count):
        students = s_count * 1250
        return """
        <div style="background: rgba(15,15,15,0.95); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); color: white; font-family: 'Montserrat', sans-serif; width: 160px; box-shadow: 0 8px 20px rgba(0,0,0,0.6); backdrop-filter: blur(8px);">
            <div style="font-size: 13px; font-weight: 800; margin-bottom: 10px; color: #fff;">■ """ + region + """</div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Branches:</span><b style="color: #FBBF24;">""" + str(b_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Schools:</span><b style="color: #38BDF8;">""" + str(s_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #aaa;"><span>Students:</span><b style="color: #4ADE80;">""" + f"{students:,}" + """</b></div>
        </div>
        """

    # Perfectly aligned latitudes/longitudes so the lines are perfectly straight horizontally/vertically
    regions_setup = [
        ("NORTH", [1.53, 103.82], [1.43, 103.82]),
        ("EAST", [1.35, 104.09], [1.35, 103.94]),
        ("WEST", [1.364, 103.58], [1.364, 103.729]),
        ("CENTRAL", [1.18, 103.82], [1.28, 103.82])
    ]

    for reg_name, box_coord, map_coord in regions_setup:
        folium.PolyLine(
            locations=[box_coord, map_coord],
            color="#00E5FF", weight=2, dash_array="5, 10", opacity=0.6
        ).add_to(m)
        
        folium.Marker(
            location=box_coord,
            icon=folium.DivIcon(html=create_box(reg_name, stats[reg_name][0], stats[reg_name][1]), icon_size=(160, 100), icon_anchor=(80, 50))
        ).add_to(m)

    m.fit_bounds([[1.15, 103.55], [1.55, 104.12]])
    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
