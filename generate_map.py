import json
import os
import csv
import folium
from folium import plugins
from folium import Element

URA_GEOJSON_PATH = "ura_regions.json"
SCHOOL_DB_PATH = "school_db.json"
MOE_DATA_PATH = "M850801_2.csv" # Updated to your new filename!
OUTPUT_MAP_PATH = "acer_expansion_map.html"

# 1. Premium High-Contrast Executive Palette (Requirement 1)
PALETTE = {
    "North": "#1E3A8A",   # Deep Royal Blue
    "West": "#059669",    # Emerald Green
    "East": "#D97706",    # Rich Amber
    "Central": "#DC2626"  # Crimson Red
}

# 2. Calculated anchors to push the text boxes into the empty sea! (Requirement 2)
REGIONS = {
    "North": {
        "color": PALETTE["North"],
        "center": [1.415, 103.820],
        "anchor": [1.475, 103.820] # Pushed straight UP into Johor Strait
    },
    "West": {
        "color": PALETTE["West"],
        "center": [1.350, 103.700],
        "anchor": [1.350, 103.560] # Pushed LEFT into the ocean
    },
    "East": {
        "color": PALETTE["East"],
        "center": [1.355, 103.940],
        "anchor": [1.355, 104.060] # Pushed RIGHT into the ocean
    },
    "Central": {
        "color": PALETTE["Central"],
        "center": [1.320, 103.825],
        "anchor": [1.240, 103.825] # Pushed DOWN south of Sentosa
    }
}

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

def generate_map():
    print("[*] Booting up Executive Infographic Engine...")
    
    if not os.path.exists(URA_GEOJSON_PATH):
        print(f"[!] ERROR: Cannot find {URA_GEOJSON_PATH}.")
        return

    branch_counts = {"North": 0, "West": 0, "East": 0, "Central": 0}
    for name in EXISTING_BRANCHES.keys():
        for region in branch_counts.keys():
            if f"({region})" in name:
                branch_counts[region] += 1

    school_counts = {"North": 0, "West": 0, "East": 0, "Central": 0}
    if os.path.exists(SCHOOL_DB_PATH):
        try:
            with open(SCHOOL_DB_PATH, 'r', encoding='utf-8') as f:
                schools = json.load(f)
                for s in schools:
                    lat, lon = s.get('lat', 0), s.get('lon', 0)
                    if lon < 103.75: school_counts["West"] += 1
                    elif lon > 103.88: school_counts["East"] += 1
                    elif lat > 1.37: school_counts["North"] += 1
                    else: school_counts["Central"] += 1
        except Exception as e:
            print(f"[!] Error reading schools: {e}")

    student_data = {"North": "N/A", "West": "N/A", "East": "N/A", "Central": "N/A"}
    if os.path.exists(MOE_DATA_PATH):
        try:
            temp_students = {"North": 0, "West": 0, "East": 0, "Central": 0}
            # Smart parser: Skips junk rows, looks for numbers linked to regions
            with open(MOE_DATA_PATH, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                for row in reader:
                    if not row or len(row) < 2: continue
                    col = row[0].strip()
                    try:
                        # Removes commas from numbers (e.g. "12,345" -> 12345)
                        val = int(row[1].replace(',', '').strip())
                    except:
                        continue 
                    
                    if "All Levels - Central" in col: temp_students["Central"] += val
                    elif "All Levels - East" in col: temp_students["East"] += val
                    elif "All Levels - North" in col and "North-East" not in col: temp_students["North"] += val
                    elif "All Levels - North-East" in col: temp_students["North"] += val
                    elif "All Levels - West" in col: temp_students["West"] += val
            
            # Only apply if data was actually found
            if sum(temp_students.values()) > 0:
                student_data = temp_students
        except Exception as e:
            print(f"[!] Error parsing MOE data: {e}")

    m = folium.Map(
        location=[1.3521, 103.8198], 
        zoom_start=11, 
        tiles=None, 
        zoom_control=False 
    )
    m.get_root().html.add_child(Element('<div style="position:fixed; top:0; left:0; width:100vw; height:100vh; background-color:#f4f4f8; z-index:-1;"></div>'))

    def style_function(feature):
        ura_region = feature['properties'].get('REGION_N', '')
        if ura_region == "WEST REGION": acer_region = "West"
        elif ura_region in ["NORTH REGION", "NORTH-EAST REGION"]: acer_region = "North"
        elif ura_region == "EAST REGION": acer_region = "East"
        elif ura_region == "CENTRAL REGION": acer_region = "Central"
        else: return {'fillOpacity': 0, 'weight': 0}

        color = PALETTE[acer_region]
        return {
            'fillColor': color,
            'color': color, 
            'weight': 1.5,
            'fillOpacity': 0.85 
        }

    with open(URA_GEOJSON_PATH, 'r') as f:
        geo_data = json.load(f)

    folium.GeoJson(geo_data, style_function=style_function).add_to(m)

    # 4. Plotting the Branches as Pins (Requirement 4)
    for name, coords in EXISTING_BRANCHES.items():
        pin_color = "#333333"
        if "(North)" in name: pin_color = PALETTE["North"]
        elif "(West)" in name: pin_color = PALETTE["West"]
        elif "(East)" in name: pin_color = PALETTE["East"]
        elif "(Central)" in name: pin_color = PALETTE["Central"]
        
        folium.CircleMarker(
            location=coords,
            radius=6,
            color="#ffffff", # Crisp white border
            weight=2,
            fill=True,
            fill_color=pin_color,
            fill_opacity=1.0,
            tooltip=name
        ).add_to(m)

    for region, config in REGIONS.items():
        color = config["color"]
        
        # Draw the tactical leader line connecting the text box to the region
        folium.PolyLine(
            locations=[config["anchor"], config["center"]],
            color="#64748b",
            weight=2,
            dash_array="4, 4",
            opacity=0.8
        ).add_to(m)
        
        # Draw a tiny dot at the end of the line on the island
        folium.CircleMarker(
            location=config["center"], radius=4, color="#ffffff", weight=1, fill=True, fill_color=color, fill_opacity=1
        ).add_to(m)

        students = student_data[region]
        student_str = f"{students:,}" if isinstance(students, int) else students

        # 3. HTML Box logic updated (Requirement 3 - added schools, removed untapped zones)
        html = f"""
        <div style="
            background: rgba(255, 255, 255, 0.98);
            border-top: 5px solid {color};
            border-radius: 6px;
            padding: 12px 16px;
            box-shadow: 0 8px 20px rgba(0,0,0,0.15);
            width: 190px;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
        ">
            <h4 style="margin: 0 0 10px 0; color: #1a1a1a; font-size: 16px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.5px;">
                <span style="color: {color};">&#11044;</span> {region}
            </h4>
            <div style="display: flex; justify-content: space-between; margin: 6px 0; font-size: 13px; color: #555;">
                <span>Branches:</span> <strong style="color: #111; font-size: 14px;">{branch_counts[region]}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin: 6px 0; font-size: 13px; color: #555;">
                <span>Schools:</span> <strong style="color: #111; font-size: 14px;">{school_counts[region]}</strong>
            </div>
            <div style="display: flex; justify-content: space-between; margin: 6px 0; font-size: 13px; color: #555;">
                <span>Est. Students:</span> <strong style="color: {color}; font-size: 14px;">{student_str}</strong>
            </div>
        </div>
        """

        # Anchor the HTML Box outside the island
        folium.Marker(
            location=config["anchor"],
            icon=folium.DivIcon(
                html=html,
                icon_size=(190, 110),
                icon_anchor=(95, 55)
            )
        ).add_to(m)

    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Premium map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
