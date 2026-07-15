import json
import os
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
    
    # Initialize the map with a premium Dark Mode aesthetic
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=12, tiles='CartoDB dark_matter')
    
    # Inject Custom CSS to force large, highly readable tooltips and popups
    custom_css = """
    <style>
    .leaflet-tooltip {
        font-size: 16px !important;
        font-weight: bold !important;
        padding: 8px 12px !important;
        background-color: rgba(30, 30, 30, 0.95) !important;
        color: white !important;
        border: 1px solid #777 !important;
        border-radius: 6px !important;
        box-shadow: 0 4px 8px rgba(0,0,0,0.4) !important;
    }
    .leaflet-popup-content {
        font-size: 15px !important;
        line-height: 1.4 !important;
    }
    .leaflet-popup-content b {
        font-size: 16px !important;
        color: #00E5FF !important;
    }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))
    
    # ==========================================
    # 2. PLOT THE SCHOOLS (DEMAND)
    # ==========================================
    print(f"[*] Plotting {len(schools)} schools...")
    
    primary_group = folium.FeatureGroup(name="Primary Schools (Light Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Green)")
    intl_group = folium.FeatureGroup(name="International Schools (Purple)")
    other_group = folium.FeatureGroup(name="Other Institutes (Gray)")
    
    for school in schools:
        level = school.get("level", "").upper()
        lat = school["lat"]
        lon = school["lon"]
        name = school["name"]
        
        # Premium Neon Colors for Dark Mode
        if "PRIMARY" in level:
            fill_color = "#4FC3F7" # Bright Cyan/Blue
            group = primary_group
        elif "SECONDARY" in level:
            fill_color = "#81C784" # Bright Green
            group = secondary_group
        elif "INTERNATIONAL" in level:
            fill_color = "#BA68C8" # Bright Purple
            group = intl_group
        else:
            fill_color = "#E0E0E0" # Light Gray
            group = other_group
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=7, # Increased from 4 for better visibility
            popup=f"<b>{name}</b><br>{level.title()}",
            tooltip=name,
            color="white", # Crisp white outline
            weight=1,
            fill_color=fill_color,
            fill=True,
            fill_opacity=0.9
        ).add_to(group)
        
    primary_group.add_to(m)
    secondary_group.add_to(m)
    intl_group.add_to(m)
    other_group.add_to(m)

    # ==========================================
    # 3. PLOT EXISTING BRANCHES & RINGS
    # ==========================================
    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & 1.5km Catchment Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        
        # Custom HTML CSS for the Gradient Star Orb
        gradient_style = (
            "background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); "
            "border-radius: 50%; width: 28px; height: 28px; display: flex; "
            "align-items: center; justify-content: center; color: white; "
            "font-size: 14px; box-shadow: 0 0 12px rgba(255,255,255,0.4); "
            "border: 2px solid white;"
        )
        icon_html = f'<div style="{gradient_style}"><i class="fa fa-star"></i></div>'
        
        # Plot the Branch Marker
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 18px; color: #FFD700;'>★</span> {name}",
            icon=folium.DivIcon(html=icon_html)
        ).add_to(branch_group)
        
        # Plot the 1.5km Cannibalization Ring (Neon Cyan)
        folium.Circle(
            location=[lat, lon],
            radius=1500, # 1.5km in meters
            popup=f"1.5km Catchment Zone for {name}",
            color="#00E5FF", # Neon Blue/Cyan edge
            weight=1.5,
            fill=True,
            fill_opacity=0.1 # Subtle translucent fill
        ).add_to(branch_group)
        
    branch_group.add_to(m)
    
    # ==========================================
    # 4. ADD FLOATING LEGEND
    # ==========================================
    legend_html = '''
    <div style="
        position: fixed; 
        bottom: 50px; left: 50px; width: 260px; height: auto; 
        background-color: rgba(30, 30, 30, 0.85); z-index:9999; font-size:14px;
        border: 1px solid #555; border-radius: 12px; padding: 15px; color: #E0E0E0;
        box-shadow: 0 8px 16px rgba(0,0,0,0.6); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        backdrop-filter: blur(5px);
        ">
        <h4 style="margin-top:0; border-bottom:1px solid #555; padding-bottom:10px; color: white; font-weight: bold;">Acer Expansion Map</h4>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); width: 20px; height: 20px; border-radius: 50%; border: 1px solid white; margin-right: 12px;"></div>
            <span style="font-weight: bold; color: white;">Acer Academy Branch</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <div style="background: rgba(0, 229, 255, 0.2); width: 20px; height: 20px; border-radius: 50%; border: 2px solid #00E5FF; margin-right: 12px;"></div>
            <span>1.5km Catchment Ring</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="background: #4FC3F7; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 15px; margin-left: 3px;"></div>
            <span>Primary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="background: #81C784; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 15px; margin-left: 3px;"></div>
            <span>Secondary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="background: #BA68C8; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 15px; margin-left: 3px;"></div>
            <span>International School</span>
        </div>
    </div>
    '''
    m.get_root().html.add_child(Element(legend_html))
    
    # Add a Layer Control panel so you can toggle different school types on/off
    folium.LayerControl().add_to(m)
    
    # Save the map to an HTML file
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Highly aesthetic interactive map generated: {OUTPUT_MAP_PATH}")
    print("    -> Run this file locally or push to GitHub to view the Dark Mode dashboard.")

if __name__ == "__main__":
    generate_map()
