import json
import os
import requests
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
    
    # Initialize the map with 'tiles=None' so we can explicitly order our base maps
    m = folium.Map(location=[1.3521, 103.8198], zoom_start=13, tiles=None)
    
    # 1. Dark Streets (This uses OpenStreetMap for maximum detail, but is inverted to Dark Mode via JS below)
    folium.TileLayer('OpenStreetMap', name='Dark Streets (Default)', show=True).add_to(m)
    
    # 2. Light Canvas
    folium.TileLayer('CartoDB positron', name='Light Canvas', show=False).add_to(m)
    
    # Inject Custom CSS to overhaul the tooltips and completely redesign the Layers Control Menu
    custom_css = """
    <style>
    /* Global Tooltip Styling */
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

    /* ====================================================
       OVERHAUL: CUSTOM BRANDED TRANSLUCENT LAYERS MENU
       ==================================================== */
    
    /* 1. Kill the ugly default white box behind the icon */
    .leaflet-control-layers {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }

    /* 2. Replace the layers icon with the Acer Academy Logo */
    .leaflet-touch .leaflet-control-layers-toggle,
    .leaflet-retina .leaflet-control-layers-toggle,
    .leaflet-control-layers-toggle {
        background-image: url('https://i.imgur.com/YhyOq9V.png') !important;
        background-size: 65% !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-color: rgba(25, 25, 25, 0.85) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border-radius: 14px !important;
        width: 55px !important;
        height: 55px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.5) !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        transition: all 0.3s ease !important;
    }
    
    .leaflet-control-layers-toggle:hover {
        background-color: rgba(40, 40, 40, 0.95) !important;
        transform: scale(1.05) !important;
        border-color: #00E5FF !important;
    }

    /* Hide Leaflet's default empty span */
    .leaflet-control-layers-toggle span {
        display: none !important;
    }

    /* 3. Frosted Glassmorphism Expanded Menu */
    .leaflet-control-layers.leaflet-control-layers-expanded {
        background: rgba(20, 20, 20, 0.85) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: 18px !important;
        padding: 22px 28px !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
        box-shadow: 0 15px 40px rgba(0,0,0,0.7) !important;
        min-width: 230px !important;
    }

    /* Menu Title */
    .leaflet-control-layers-list::before {
        content: "Map Display Settings";
        display: block;
        font-size: 16px;
        font-weight: 700;
        color: #00E5FF; /* Glowing Cyan */
        text-transform: uppercase;
        letter-spacing: 1px;
        margin-bottom: 15px;
        border-bottom: 1px solid rgba(255,255,255,0.15);
        padding-bottom: 10px;
    }

    /* Text & Spacing */
    .leaflet-control-layers-list {
        font-size: 15px !important;
        margin-bottom: 0 !important;
    }
    
    .leaflet-control-layers-base label,
    .leaflet-control-layers-overlays label {
        display: flex !important;
        align-items: center !important;
        margin: 14px 0 !important;
        cursor: pointer !important;
        font-weight: 500 !important;
        transition: color 0.2s !important;
    }

    .leaflet-control-layers-base label:hover,
    .leaflet-control-layers-overlays label:hover {
        color: #FFD700 !important; /* Gold hover effect */
    }

    /* Separator */
    .leaflet-control-layers-separator {
        border-top: 1px solid rgba(255,255,255,0.15) !important;
        margin: 18px 0 !important;
    }

    /* Custom Checkboxes & Radio Buttons */
    input[type="checkbox"].leaflet-control-layers-selector,
    input[type="radio"].leaflet-control-layers-selector {
        appearance: none;
        -webkit-appearance: none;
        width: 18px !important;
        height: 18px !important;
        border: 2px solid #888 !important;
        border-radius: 4px;
        margin-right: 12px !important;
        cursor: pointer !important;
        position: relative;
        background: rgba(255,255,255,0.1);
        transition: all 0.2s;
    }

    input[type="radio"].leaflet-control-layers-selector {
        border-radius: 50%;
    }

    input[type="checkbox"].leaflet-control-layers-selector:checked,
    input[type="radio"].leaflet-control-layers-selector:checked {
        background: #00E5FF !important;
        border-color: #00E5FF !important;
    }

    input[type="checkbox"].leaflet-control-layers-selector:checked::after {
        content: "✔";
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        color: #000;
        font-size: 12px;
        font-weight: bold;
    }

    input[type="radio"].leaflet-control-layers-selector:checked::after {
        content: "";
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        width: 8px;
        height: 8px;
        background: #000;
        border-radius: 50%;
    }
    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    # Safely draw a subtle dashed border around the mainland of Singapore
    sg_border_url = "https://raw.githubusercontent.com/johan/world.geo.json/master/countries/SGP.geo.json"
    try:
        print("[*] Fetching Singapore geographic boundaries...")
        res = requests.get(sg_border_url, timeout=10)
        if res.status_code == 200:
            folium.GeoJson(
                res.json(),
                name="Singapore Mainland Border",
                style_function=lambda feature: {
                    'fillColor': 'none',
                    'color': '#9E9E9E', # Subtle grey outline that works on all modes
                    'weight': 2,
                    'dashArray': '6, 6'
                }
            ).add_to(m)
        else:
            print(f"[!] Warning: Could not fetch borders (HTTP {res.status_code}). Skipping boundary layer.")
    except Exception as e:
        print(f"[!] Warning: Network error fetching borders ({e}). Skipping boundary layer.")
    
    print(f"[*] Plotting {len(schools)} schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)")
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)")
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)")
    other_group = folium.FeatureGroup(name="Other Institutes (Gray)")
    
    for school in schools:
        level = school.get("level", "").upper()
        lat = school["lat"]
        lon = school["lon"]
        name = school["name"]
        
        # Beautiful, modern soft-neon palette that pops nicely
        if "PRIMARY" in level:
            fill_color = "#38BDF8" # Sky Blue
            group = primary_group
        elif "SECONDARY" in level:
            fill_color = "#A78BFA" # Soft Violet
            group = secondary_group
        elif "INTERNATIONAL" in level:
            fill_color = "#F472B6" # Rose Pink
            group = intl_group
        else:
            fill_color = "#9CA3AF" # Cool Gray
            group = other_group
            
        folium.CircleMarker(
            location=[lat, lon],
            radius=7, 
            popup=f"<b style='color: {fill_color}'>{name}</b><br>{level.title()}",
            tooltip=f"<span style='font-size: 15px;'>{name}</span>",
            color="white", # Crisp white outline
            weight=1,
            fill_color=fill_color,
            fill=True,
            fill_opacity=0.85
        ).add_to(group)
        
    primary_group.add_to(m)
    secondary_group.add_to(m)
    intl_group.add_to(m)
    other_group.add_to(m)

    print(f"[*] Plotting {len(EXISTING_BRANCHES)} Acer Academy Branches & 1.5km Radius Rings...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    
    for name, (lat, lon) in EXISTING_BRANCHES.items():
        
        # Premium Brand Dot for the actual store location
        gradient_style = (
            "background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); "
            "border-radius: 50%; width: 28px; height: 28px; display: flex; "
            "align-items: center; justify-content: center; color: white; "
            "font-size: 14px; box-shadow: 0 0 12px rgba(0,0,0,0.5); "
            "border: 2px solid white; overflow: hidden;"
        )
        
        logo_url = "https://i.imgur.com/YhyOq9V.png"
        icon_html = f'<div style="{gradient_style}"><img src="{logo_url}" style="width: 100%; object-fit: contain;"></div>'
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b style='color: #FF9800;'>ACER ACADEMY</b><br>{name}",
            tooltip=f"<span style='font-size: 18px; font-weight: bold; white-space: nowrap;'>★ {name}</span>",
            icon=folium.DivIcon(html=icon_html, icon_size=(28, 28), icon_anchor=(14, 14))
        ).add_to(branch_group)
        
        # 1.5km Catchment Ring - Electric Cyan
        folium.Circle(
            location=[lat, lon],
            radius=1500, # 1.5km in meters
            popup=f"1.5km Radius Ring for {name}",
            color="#00C9FF", # Premium Glowing Electric Cyan
            weight=2,
            fill_color="#00C9FF",
            fill_opacity=0.18 # Highly translucent but clearly visible
        ).add_to(branch_group)
        
    branch_group.add_to(m)
    
    # Live Dark Mode JS Engine + Legend HTML
    legend_html = '''
    <div id="legend-box" style="
        position: fixed; 
        bottom: 50px; left: 50px; width: 260px; height: auto; 
        background-color: rgba(20, 20, 20, 0.85); z-index:9999; font-size:14px;
        border: 1px solid rgba(255,255,255,0.15); border-radius: 16px; padding: 20px; color: #E0E0E0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.6); font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
        transition: all 0.3s ease;
        ">
        <h4 style="margin-top:0; border-bottom:1px solid rgba(255,255,255,0.15); padding-bottom:12px; color: #00E5FF; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; font-size: 15px;">Expansion Map</h4>
        
        <div style="display: flex; align-items: center; margin-bottom: 14px; margin-top: 15px;">
            <div style="background: linear-gradient(135deg, #FFD700, #00E5FF, #00FF00, #FF3D00); width: 22px; height: 22px; border-radius: 50%; border: 1px solid white; margin-right: 14px; display: flex; justify-content: center; align-items: center; overflow: hidden; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%;">
            </div>
            <span class="legend-text" style="font-weight: bold; color: white;">Acer Academy</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 18px;">
            <div style="width: 22px; height: 22px; border-radius: 50%; padding: 2px; background: #00C9FF; margin-right: 14px; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 5px rgba(0,0,0,0.5);">
                <div id="legend-ring-inner" style="width: 100%; height: 100%; border-radius: 50%; background: rgba(20, 20, 20, 0.85);"></div>
            </div>
            <span class="legend-text" style="color: white;">1.5km Radius Ring</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: #38BDF8; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">Primary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 12px;">
            <div style="background: #A78BFA; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">Secondary School</span>
        </div>
        
        <div style="display: flex; align-items: center; margin-bottom: 5px;">
            <div style="background: #F472B6; width: 14px; height: 14px; border-radius: 50%; border: 1px solid white; margin-right: 18px; margin-left: 4px;"></div>
            <span class="legend-text" style="color: white; font-weight: 500;">International School</span>
        </div>
    </div>
    
    <script>
    // The "Invert Trick" Engine
    // This script takes the ultra-detailed OpenStreetMap base layer and inverts its colors.
    // We apply a 100% grayscale filter first to completely strip out the ugly red/yellow highways,
    // resulting in a perfectly clean, high-contrast monochrome Dark Mode!
    document.addEventListener("DOMContentLoaded", function() {
        var map = null;
        for (var key in window) {
            if (key.startsWith('map_')) { map = window[key]; break; }
        }
        if (map) {
            var tilePane = document.querySelector('.leaflet-tile-pane');
            
            // Apply the custom Monochrome Dark Mode filter
            tilePane.style.filter = 'grayscale(100%) invert(100%) brightness(95%) contrast(115%)';

            map.on('baselayerchange', function(e) {
                var legend = document.getElementById('legend-box');
                var title = legend ? legend.querySelector('h4') : null;
                var innerRing = document.getElementById('legend-ring-inner');
                var spans = legend ? legend.querySelectorAll('span.legend-text') : [];
                
                if (e.name === 'Light Canvas') {
                    // Clean Grayscale Light Mode
                    tilePane.style.filter = 'grayscale(100%) brightness(1) contrast(1.05)';
                    if (legend) {
                        legend.style.backgroundColor = 'rgba(255, 255, 255, 0.9)';
                        legend.style.borderColor = '#ccc';
                        title.style.color = '#111';
                        title.style.borderBottom = '1px solid #ccc';
                        spans.forEach(s => s.style.color = '#333');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                    }
                } else {
                    // Re-apply the magical Monochrome Dark Mode filter
                    tilePane.style.filter = 'grayscale(100%) invert(100%) brightness(95%) contrast(115%)';
                    if (legend) {
                        legend.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                        legend.style.borderColor = 'rgba(255,255,255,0.15)';
                        title.style.color = '#00E5FF';
                        title.style.borderBottom = '1px solid rgba(255,255,255,0.15)';
                        spans.forEach(s => s.style.color = 'white');
                        if (innerRing) innerRing.style.backgroundColor = 'rgba(20, 20, 20, 0.85)';
                    }
                }
            });
        }
    });
    </script>
    '''
    m.get_root().html.add_child(Element(legend_html))
    
    # Add a Layer Control panel so you can toggle maps and school types on/off
    folium.LayerControl(position='topright').add_to(m)
    
    # Save the map to an HTML file
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
