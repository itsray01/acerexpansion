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
    if not os.path.exists(SCHOOL_DB_PATH):
        print(f"[!] Cannot find {SCHOOL_DB_PATH}. Run build_school_db.py first!")
        return []
    with open(SCHOOL_DB_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_map():
    print("[*] Booting up Map Engine...")
    schools = load_schools()
    if not schools: return
    
    # Initialize the map. Zoom=13 brings it 150% closer than the previous Zoom=12
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=13)
    
    # Add Dark and Light Mode base maps (the user can toggle them in the top right)
    folium.TileLayer('CartoDB dark_matter', name='Dark Mode').add_to(m)
    folium.TileLayer('CartoDB positron', name='Light Mode').add_to(m)
    
    # Inject Custom CSS to force large, highly readable tooltips globally
    custom_css = """
    <style>
    .leaflet-tooltip {
        font-size: 16px !important;
        font-weight: bold !important;
        padding: 10px 14px !important;
        background-color: rgba(20, 20, 20, 0.95) !important;
        color: white !important;
        border: 1px solid #888 !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.5) !important;
    }
    .leaflet-popup-content { font-size: 15px !important; line-height: 1.4 !important; }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    # --- NEW: INJECT SVG GRADIENT FOR THE 1.5KM RINGS ---
    # This allows Folium vector shapes (circles) to use true multi-color CSS-style gradients!
    svg_gradient = """
    <svg style="width:0; height:0; position:absolute;" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="ringGradient" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="#FFD700" />
          <stop offset="33%" stop-color="#00E5FF" />
          <stop offset="66%" stop-color="#00FF00" />
          <stop offset="100%" stop-color="#FF3D00" />
        </linearGradient>
      </defs>
    </svg>
    """
    m.get_root().html.add_child(Element(svg_gradient))

    # Draw a subtle dashed border around the mainland of Singapore
    sg_border_url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/SGP.geo.json"
    folium.GeoJson(
        sg_border_url,
        name="Singapore Mainland Border",
        style_function=lambda feature: {
            'fillColor': 'none',
            'color': '#9E9E9E', # Subtle grey outline that works on both light/dark mode
            'weight': 2,
            'dashArray': '6, 6'
        }
    ).add_to(m)
    
    print(f"[*] Plotting {len(schools)} schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Green)")
    intl_group = folium.FeatureGroup(name="International Schools (Purple)")
    other_group = folium.FeatureGroup(name="Other Institutes (Gray)")
    
    for school in schools:
        level = school.get("level", "").upper()
        lat = school["lat"]
        lon = school["lon"]
        name = school["name"]
        
        # We use high-contrast vivid colors so they pop on BOTH light and dark mode
        if "PRIMARY" in level:
            fill_color = "#1E88E5" # Vivid Blue
            group = primary_group
        elif "SECONDARY" in level:
            fill_color = "#43A047" # Vivid Green
            group = secondary_group
        elif "INTERNATIONAL" in level:
            fill_color = "#8E24AA" # Vivid Purple
            group = intl_group
        else:
            fill_color = "#757575" # Gray
            group = other_group
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=7, # Larger dots
            popup=f"<b style='color: {fill_color}'>{name}</b><br>{level.title()}",
            tooltip=f"<span style='font-size: 15px;'>{name}</span>",
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

    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & 1.5km Radius Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        
        # New Gradient (Yellow -> Blue -> Green -> Red)
        gradient_style = (
            "background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); "
            "border-radius: 50%; width: 28px; height: 28px; display: flex; "
            "align-items: center; justify-content: center; color: white; "
            "font-size: 14px; box-shadow: 0 0 12px rgba(0,0,0,0.5); "
            "border: 2px solid white; overflow: hidden;"
        )
        
        # Pulls your transparent logo and wraps it perfectly inside the gradient circle
        logo_url = "https://i.imgur.com/YhyOq9V.png"
        icon_html = f'<div style="{gradient_style}"><img src="{logo_url}" style="width: 100%; object-fit: contain;"></div>'
        
        # Plot the Branch Marker (Perfectly centered using icon_anchor)
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 18px; font-weight: bold; white-space: nowrap;'>★ {name}</span>",
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
        ).add_to(branch_group)
        
        # Plot the 1.5km Radius Ring (Now using the SVG Gradient!)
        folium.Circle(
            location=[lat, lon],
            radius=1500, # 1.5km in meters
            popup=f"1.5km Radius Ring for {name}",
            color="url(#ringGradient)", # Targets the custom injected SVG block
            weight=2,
            fill_color="url(#ringGradient)",
            fill_opacity=0.15 # Still beautifully transparent
        ).add_to(branch_group)
        
    branch_group.add_to(m)
    
    # Dynamic Floating Legend that automatically swaps colors if Light Mode is turned on
    legend_html = '''
    <div id="legend-box" style="
        position: fixed; 
        bottom: 50px; left: 50px; width: 260px; height: auto; 
        background-color: rgba(30, 30, 30, 0.85); z-index:9999; font-size:14px;
        border: 1px solid #555; border-radius: 12px; padding: 15px; color: #E0E0E0;
        box-shadow: 0 8px 16px rgba(0,0,0,0.6); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        backdrop-filter: blur(5px); transition: all 0.3s ease;
        ">
        <h4 style="margin-top:0; border-bottom:1px solid #555; padding-bottom:10px; color: white; font-weight: bold;">Acer Expansion Map</h4>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); width: 20px; height: 20px; border-radius: 50%; border: 1px solid white; margin-right: 12px; display: flex; justify-content: center; align-items: center; overflow: hidden;">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%;">
            </div>
            <span class="legend-text" style="font-weight: bold; color: white;">Acer Academy Branch</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 15px;">
            <div style="width: 20px; height: 20px; border-radius: 50%; padding: 2px; background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); margin-right: 12px; display: flex; align-items: center; justify-content: center;">
                <div id="legend-ring-inner" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(30, 30, 30, 0.85);"></div>
            </div>
            <span class="legend-text" style="color: white;">1.5km Radius Ring</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="background: #1E88E5; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 15px; margin-left: 3px;"></div>
            <span class="legend-text" style="color: white;">Primary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="background: #43A047; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 15px; margin-left: 3px;"></div>
            <span class="legend-text" style="color: white;">Secondary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="background: #8E24AA; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 15px; margin-left: 3px;"></div>
            <span class="legend-text" style="color: white;">International School</span>
        </div>
    </div>
    
    <script>
    // This script listens for the user clicking the layer control in the top right.
    // If they switch to Light Mode, it automatically flips the colors of the legend!
    document.addEventListener("DOMContentLoaded", function() {
        var map = null;
        for (var key in window) {
            if (key.startsWith('map_')) { map = window[key]; break; }
        }
        if (map) {
            map.on('baselayerchange', function(e) {
                var legend = document.getElementById('legend-box');
                if (legend) {
                    var spans = legend.querySelectorAll('span.legend-text');
                    var title = legend.querySelector('h4');
                    var innerRing = document.getElementById('legend-ring-inner');
                    
                    if (e.name === 'Light Mode') {
                        legend.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                        legend.style.borderColor = '#ccc';
                        title.style.color = '#111';
                        title.style.borderBottom = '1px solid #ccc';
                        spans.forEach(s => s.style.color = '#333');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                    } else {
                        legend.style.backgroundColor = 'rgba(30, 30, 30, 0.85)';
                        legend.style.borderColor = '#555';
                        title.style.color = 'white';
                        title.style.borderBottom = '1px solid #555';
                        spans.forEach(s => s.style.color = 'white');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(30, 30, 30, 0.85)';
                    }
                }
            });
        }
    });
    </script>
    '''
    m.get_root().html.add_child(Element(legend_html))
    
    # Add a Layer Control panel so you can toggle Light/Dark mode and school types on/off
    folium.LayerControl(position='topright').add_to(m)
    
    # Save the map to an HTML file
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
