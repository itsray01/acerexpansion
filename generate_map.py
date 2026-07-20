import os
import csv
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
    """Reads directly from the Geocoded CSV database."""
    schools = []
    
    if os.path.exists("All_Schools_Geocoded.csv"):
        print("[*] Found All_Schools_Geocoded.csv! Loading...")
        with open("All_Schools_Geocoded.csv", 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                name_key = next((k for k in row.keys() if 'name' in str(k).lower() or 'school' in str(k).lower()), None)
                level_key = next((k for k in row.keys() if 'level' in str(k).lower()), None)
                
                if name_key and row.get('lat') and row.get('lon'):
                    try:
                        schools.append({
                            "name": row[name_key],
                            "lat": float(row['lat']),
                            "lon": float(row['lon']),
                            "level": row[level_key] if level_key and row[level_key] else "PRIMARY"
                        })
                    except ValueError:
                        continue
        print(f"[+] Successfully loaded {len(schools)} schools from CSV.")
        return schools
        
    print("[!] CRITICAL: All_Schools_Geocoded.csv not found.")
    return []

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    if not schools: 
        print("[!] No schools loaded. Terminating map generation.")
        return
    
    # Natively loading the dark map so NO javascript inversion is needed!
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles='CartoDB dark_matter')

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

    /* Custom Layer Control Menu (Click-to-Open) */
    .leaflet-control-layers {
        border: none !important; background: transparent !important; box-shadow: none !important;
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
    .leaflet-control-layers.leaflet-control-layers-expanded {
        background: rgba(20, 20, 20, 0.90) !important;
        backdrop-filter: blur(16px) !important; color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.15) !important; border-radius: 18px !important;
        padding: 22px 28px !important; font-family: 'Montserrat', sans-serif !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important; min-width: 230px !important;
    }

    /* Executive Dashboard */
    .acer-dashboard {
        position: fixed; top: 20px; right: 80px; z-index: 9999;
        background: rgba(20,20,20,0.85); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        padding: 20px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.15);
        color: white; font-family: 'Montserrat', sans-serif; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 280px;
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
                    'color': 'transparent', # Removes the jarring white line
                    'weight': 0,
                    'fillOpacity': 0.35
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
    
    # Dynamic Stat Trackers for the Regional Boxes
    stats = {"NORTH": [0,0], "EAST": [0,0], "WEST": [0,0], "CENTRAL": [0,0]}

    for school in schools:
        level = school.get("level", "").upper()
        # Micro-jitter to prevent dots from stacking infinitely on top of each other
        lat = school["lat"] + random.uniform(-0.0008, 0.0008)
        lon = school["lon"] + random.uniform(-0.0008, 0.0008)
        name = school["name"]
        
        # Region Tracking
        if lat > 1.41: stats["NORTH"][1] += 1
        elif lon > 103.89: stats["EAST"][1] += 1
        elif lon < 103.78: stats["WEST"][1] += 1
        else: stats["CENTRAL"][1] += 1
        
        if "PRIMARY" in level:
            fill_color, group = "#38BDF8", primary_group
        elif "SECONDARY" in level:
            fill_color, group = "#A78BFA", secondary_group
        elif "JUNIOR COLLEGE" in level:
            fill_color, group = "#FBBF24", jc_group
        elif "INTERNATIONAL" in level:
            fill_color, group = "#F472B6", intl_group
        else:
            continue
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=6, 
            popup=f"<b style='color: {fill_color}'>{name}</b><br>{level.title()}",
            tooltip=f"{name}", color="white", weight=1, fill_color=fill_color, fill=True, fill_opacity=0.85
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
        
        # CSS Background is explicitly set to transparent!
        icon_html = """
        <div style="background-color: transparent; border-radius: 8px; width: 32px; height: 32px; display: flex; align-items: center; justify-content: center; border: 2px solid #ffffff; box-shadow: 0 4px 10px rgba(0,0,0,0.5); overflow: hidden;">
            <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; height: 100%; object-fit: contain;">
        </div>
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"★ {name}",
            icon=folium.DivIcon(html=icon_html, icon_size=(32, 32), icon_anchor=(16, 16))
        ).add_to(branch_group)
        
        # Cyan 1.5km protective radius
        folium.Circle(
            location=[lat, lon],
            radius=1500, color="#00C9FF", weight=2, fill_color="#00C9FF", fill_opacity=0.18
        ).add_to(branch_group)
    branch_group.add_to(m)

    def create_box(region, b_count, s_count):
        students = s_count * 1250 # Estimation algorithm
        return """
        <div style="background: rgba(15,15,15,0.95); padding: 15px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); color: white; font-family: 'Montserrat', sans-serif; width: 160px; box-shadow: 0 8px 20px rgba(0,0,0,0.6); backdrop-filter: blur(8px);">
            <div style="font-size: 13px; font-weight: 800; margin-bottom: 10px; color: #fff;">■ """ + region + """</div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Branches:</span><b style="color: #FBBF24;">""" + str(b_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; color: #aaa;"><span>Schools:</span><b style="color: #38BDF8;">""" + str(s_count) + """</b></div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; color: #aaa;"><span>Students:</span><b style="color: #4ADE80;">""" + f"{students:,}" + """</b></div>
        </div>
        """

    # Coordinates configured so that X or Y match perfectly to draw a 100% straight line
    regions_setup = [
        # North Box (Far up) -> points straight DOWN to Yishun
        ("NORTH", [1.49, 103.82], [1.43, 103.82]),
        # East Box (Far Right) -> points straight LEFT to Tampines
        ("EAST", [1.35, 104.04], [1.35, 103.94]),
        # West Box (Far Left) -> points straight RIGHT to Tengah
        ("WEST", [1.364, 103.62], [1.364, 103.729]),
        # Central Box (Far Down) -> points straight UP to Bukit Merah
        ("CENTRAL", [1.22, 103.82], [1.28, 103.82])
    ]

    for reg_name, box_coord, map_coord in regions_setup:
        # 1. The Perfectly Straight Dotted Line
        folium.PolyLine(
            locations=[box_coord, map_coord],
            color="#00E5FF", weight=2, dash_array="5, 10", opacity=0.6
        ).add_to(m)
        
        # 2. The Floating Data Box
        folium.Marker(
            location=box_coord,
            icon=folium.DivIcon(html=create_box(reg_name, stats[reg_name][0], stats[reg_name][1]), icon_size=(160, 100), icon_anchor=(80, 50))
        ).add_to(m)

    dashboard_html = """
    <div class="acer-dashboard">
        <h4 style="margin: 0 0 15px 0; font-size: 16px; font-weight: 800; display: flex; align-items: center; gap: 10px;">
            <div style="width: 24px; height: 24px; border-radius: 6px; border: 1px solid #fff; display: flex; align-items: center; justify-content: center; overflow: hidden; background: transparent;">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width:100%; height:100%; object-fit: cover;">
            </div>
            ACER <span style="color:#ff3344;">EXPANSION</span>
        </h4>
        <div style="font-size: 12px; color: #ccc; line-height: 1.5;">
            Analyzing <b style="color:#fff;">""" + str(len(schools)) + """</b> educational zones across <b style="color:#fff;">""" + str(len(EXISTING_BRANCHES)) + """</b> active branches.
        </div>
        <div style="display:flex; justify-content:space-between; font-size:10px; font-weight:700; color:#aaa; margin-top:14px; text-transform:uppercase;">
            <span>Network Status</span><span style="color:#4ADE80;">Total Coverage</span>
        </div>
        <div style="width: 100%; height: 6px; background: rgba(255,255,255,0.1); border-radius: 3px; margin-top: 5px; overflow: hidden;">
            <div style="width: 100%; height: 100%; background: #4ADE80; border-radius: 3px;"></div>
        </div>
    </div>
    """
    m.get_root().html.add_child(Element(dashboard_html))

    folium.LayerControl(position='topright', collapsed=True).add_to(m)
    
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
