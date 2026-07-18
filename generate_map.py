import json
import os
import folium
from folium import plugins
from folium import Element

# ==========================================
# 1. CONFIGURATION
# ==========================================
URA_GEOJSON_PATH = "ura_regions.json"  # The file you just created!
OUTPUT_MAP_PATH = "acer_expansion_map.html"

# Acer Academy 4-Region Pastel Palette
PALETTE = {
    "North": "#6b8ca3",   # Slate Teal (Combines North & North-East)
    "West": "#a2b5d4",    # Pastel Blue
    "East": "#d96c9c",    # Dusty Rose
    "Central": "#a6d5c6"  # Mint Green
}

# Approximate visual centers to drop our DivIcon labels
REGION_CENTERS = {
    "North": [1.415, 103.820],
    "West": [1.350, 103.700],
    "East": [1.355, 103.940],
    "Central": [1.295, 103.825]
}

# ==========================================
# 2. MAP BUILDER
# ==========================================
def generate_map():
    print("[*] Booting up Infographic Map Engine...")
    
    if not os.path.exists(URA_GEOJSON_PATH):
        print(f"[!] ERROR: Cannot find {URA_GEOJSON_PATH}. Please save the JSON data first!")
        return

    # Initialize a BLANK canvas (no Google/OSM streets)
    m = folium.Map(
        location=[1.3521, 103.8198], 
        zoom_start=12, 
        tiles=None, # Removes all roads and backgrounds
        zoom_control=False # Hides the +/- buttons for a cleaner look
    )
    
    # Add a solid off-white background color
    m.get_root().html.add_child(Element('<div style="position:fixed; top:0; left:0; width:100vw; height:100vh; background-color:#f8f9fa; z-index:-1;"></div>'))

    # ==========================================
    # INJECT CUSTOM CSS FOR DIVICONS
    # ==========================================
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&display=swap');

    /* The DivIcon container */
    .info-label-container {
        position: relative;
        font-family: 'Montserrat', sans-serif;
    }

    /* The Text Box */
    .info-box {
        position: absolute;
        background: rgba(255, 255, 255, 0.95);
        border-radius: 8px;
        padding: 12px 16px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        min-width: 160px;
        z-index: 1000;
        backdrop-filter: blur(5px);
        border-left: 4px solid #333; /* Dynamic color overridden in inline style */
    }

    .info-box h4 {
        margin: 0 0 8px 0;
        font-size: 16px;
        font-weight: 800;
        letter-spacing: 1px;
        color: #1a1a1a;
        text-transform: uppercase;
    }

    .info-box p {
        margin: 4px 0;
        font-size: 12px;
        font-weight: 600;
        color: #555;
        display: flex;
        justify-content: space-between;
    }
    
    .info-box p span {
        font-weight: 800;
        color: #1a1a1a;
    }

    /* The Angled Leader Line Trick */
    .leader-line {
        position: absolute;
        width: 60px;
        height: 60px;
        border-bottom: 2px solid #666;
        border-right: 2px solid #666;
        z-index: 999;
    }
    
    /* Specific line routing based on region */
    .line-north { top: 20px; left: 0px; width: 40px; height: 30px; border-bottom: none; border-right: none; border-top: 2px solid #666; border-left: 2px solid #666; }
    .line-west  { top: -40px; left: 20px; width: 60px; height: 60px; border-top: 2px solid #666; border-left: 2px solid #666; border-bottom: none; border-right: none; }
    .line-east  { top: -40px; right: 20px; width: 60px; height: 60px; border-top: 2px solid #666; border-right: 2px solid #666; border-bottom: none; border-left: none; }
    .line-central{ bottom: 20px; left: 20px; width: 40px; height: 40px; border-bottom: 2px solid #666; border-left: 2px solid #666; border-top: none; border-right: none; }

    </style>
    """
    m.get_root().header.add_child(Element(custom_css))

    # ==========================================
    # PARSE & STYLE THE GEOJSON
    # ==========================================
    def style_function(feature):
        # 1. Read the government region from the JSON
        ura_region = feature['properties'].get('REGION_N', '')
        
        # 2. Map it to Acer Academy's 4 Regions
        if ura_region == "WEST REGION": 
            acer_region = "West"
        elif ura_region in ["NORTH REGION", "NORTH-EAST REGION"]: 
            acer_region = "North"
        elif ura_region == "EAST REGION": 
            acer_region = "East"
        elif ura_region == "CENTRAL REGION": 
            acer_region = "Central"
        else:
            return {'fillOpacity': 0, 'weight': 0} # Hide islands/sea

        color = PALETTE[acer_region]

        # 3. By making the border (color) the EXACT SAME as the fill (fillColor), 
        # the internal neighborhood borders disappear, creating one solid puzzle piece!
        return {
            'fillColor': color,
            'color': color,
            'weight': 1.5,
            'fillOpacity': 1.0
        }

    print("[*] Drawing solid geometry...")
    with open(URA_GEOJSON_PATH, 'r') as f:
        geo_data = json.load(f)

    folium.GeoJson(
        geo_data,
        name="Acer Regions",
        style_function=style_function
    ).add_to(m)

    # ==========================================
    # PLACE THE DIVICON LABELS
    # ==========================================
    print("[*] Injecting DivIcon leader lines...")
    
    # Dummy data for now - we will connect this to your school database later!
    metrics = {
        "North": {"centers": 4, "unprotected": 12},
        "West": {"centers": 3, "unprotected": 24},
        "East": {"centers": 4, "unprotected": 8},
        "Central": {"centers": 6, "unprotected": 3}
    }

    for region, coords in REGION_CENTERS.items():
        color = PALETTE[region]
        data = metrics[region]
        
        # Determine how to push the box away from the center point
        if region == "North": box_pos = "top: -60px; left: -180px;"
        elif region == "West": box_pos = "top: -90px; left: -190px;"
        elif region == "East": box_pos = "top: -90px; left: 80px;"
        elif region == "Central": box_pos = "top: 60px; left: -100px;"

        # The actual HTML injected directly onto the map canvas
        icon_html = f"""
        <div class="info-label-container">
            <div class="leader-line line-{region.lower()}"></div>
            <div class="info-box" style="border-left-color: {color}; {box_pos}">
                <h4 style="color: {color}">{region}</h4>
                <p>Branches: <span>{data['centers']}</span></p>
                <p>Untapped Zones: <span style="color: #FF3D00;">{data['unprotected']}</span></p>
            </div>
        </div>
        """

        folium.Marker(
            location=coords,
            icon=folium.DivIcon(
                html=icon_html,
                icon_size=(0, 0), # Forces the icon to originate exactly at the GPS point
                icon_anchor=(0, 0)
            )
        ).add_to(m)

    # Save the map
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Infographic map generated: {OUTPUT_MAP_PATH}")
    print("    -> Open this file in your web browser to see the results.")

if __name__ == "__main__":
    generate_map()
