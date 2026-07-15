import json
import os
import folium
from folium import plugins

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
    "Aljunied (East)": (1.321506345667894, 103.88726075133513),
    "Elias Mall (East)": (1.3773, 103.9424),
    "Dawson (Central)": (1.2941, 103.8099),
    "Depot Heights (Central)": (1.2809, 103.8086),
    "Tiong Bahru (Central)": (1.2861739679441766, 103.82850623578356),
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
    
    # Initialize the map centered on Singapore
    # We use a clean, modern base layer (CartoDB positron) so the pins pop out
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles='CartoDB positron')
    
    # ==========================================
    # 2. PLOT THE SCHOOLS (DEMAND)
    # ==========================================
    print(f"[*] Plotting {len(schools)} schools...")
    
    # We will put schools in FeatureGroups so they can be toggled on/off in the map UI
    primary_group = folium.FeatureGroup(name="Primary Schools (Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Green)")
    intl_group = folium.FeatureGroup(name="International Schools (Purple)")
    other_group = folium.FeatureGroup(name="Other Institutes (Gray)")
    
    for school in schools:
        level = school.get("level", "").upper()
        lat = school["lat"]
        lon = school["lon"]
        name = school["name"]
        
        # Determine Color and Group based on Academic Level
        if "PRIMARY" in level:
            color = "blue"
            group = primary_group
        elif "SECONDARY" in level:
            color = "green"
            group = secondary_group
        elif "INTERNATIONAL" in level:
            color = "purple"
            group = intl_group
        else:
            color = "lightgray"
            group = other_group
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            popup=f"<b>{name}</b><br>{level.title()}",
            tooltip=name,
            color=color,
            fill=True,
            fill_opacity=0.7
        ).add_to(group)
        
    # Add groups to map
    primary_group.add_to(m)
    secondary_group.add_to(m)
    intl_group.add_to(m)
    other_group.add_to(m)

    # ==========================================
    # 3. PLOT EXISTING BRANCHES (SUPPLY & CANNIBALIZATION)
    # ==========================================
    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & 1.5km Catchment Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches (Red Stars)", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        # Plot the Branch Marker (Red Star)
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>ACER ACADEMY</b><br>{name}",
            tooltip=name,
            icon=folium.Icon(color="red", icon="star", prefix="fa")
        ).add_to(branch_group)
        
        # Plot the 1.5km Cannibalization Ring
        folium.Circle(
            location=[lat, lon],
            radius=1500, # 1.5km in meters
            popup=f"1.5km Catchment Zone for {name}",
            color="red",
            weight=1,
            fill=True,
            fill_opacity=0.15 # Highly translucent so you can still see the map underneath
        ).add_to(branch_group)
        
    branch_group.add_to(m)
    
    # Add a Layer Control panel so you can toggle different school types on/off
    folium.LayerControl().add_to(m)
    
    # Save the map to an HTML file
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")
    print("    -> Double-click this HTML file to open it in Chrome/Safari.")

if __name__ == "__main__":
    generate_map()
