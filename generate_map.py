import folium
from folium import plugins
import pandas as pd
import json
import os
import requests
import math

def generate_map():
    print("[*] Booting up Map Engine...")

    # ==========================================
    # 1. LOAD DATA SOURCES
    # ==========================================
    
    # A. Acer Academy Existing Branches
    EXISTING_BRANCHES = {
        "Woodlands": (1.4366, 103.7865),
        "Bukit Panjang": (1.3789, 103.7621),
        "Choa Chu Kang": (1.3846, 103.7447),
        "Jurong East": (1.3331, 103.7423),
        "Clementi": (1.3140, 103.7624),
        "Bukit Timah": (1.3275, 103.8066),
        "Toa Payoh": (1.3323, 103.8475),
        "Bishan": (1.3496, 103.8492),
        "Ang Mo Kio": (1.3694, 103.8499),
        "Yishun": (1.4284, 103.8354),
        "Sengkang": (1.3917, 103.8945),
        "Punggol": (1.4052, 103.9024),
        "Hougang": (1.3725, 103.8925),
        "Serangoon": (1.3496, 103.8732),
        "Tampines": (1.3524, 103.9440),
        "Pasir Ris": (1.3721, 103.9491),
        "Bedok": (1.3236, 103.9273),
        "Marine Parade": (1.3026, 103.9048),
        "Paya Lebar": (1.3175, 103.8926)
    }

    # B. Load School Database
    print("[*] Loading exact GPS coordinates from local school_db.json...")
    schools_data = []
    if os.path.exists("school_db.json"):
        with open("school_db.json", "r", encoding="utf-8") as f:
            schools_data = json.load(f)
    print(f"[+] Successfully loaded {len(schools_data)} schools with strict pinpoint accuracy.")

    # ==========================================
    # 2. INITIALIZE PREMIUM MAP (Business Times Style)
    # ==========================================
    m = folium.Map(
        location=[1.3521, 103.8198],
        zoom_start=12,
        tiles=None, # We use custom tiles below
        control_scale=True,
        max_bounds=True
    )

    # Adding "Dark Mode" specifically for heatmap contrast
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        name='Dark Streets (Default)',
        control=True
    ).add_to(m)
    
    # Adding a clean light canvas for editorial look
    folium.TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
        name='Light Canvas',
        control=True,
        show=False
    ).add_to(m)

    # Standard map just in case
    folium.TileLayer('openstreetmap', name='Standard Map', show=False).add_to(m)

    # ==========================================
    # 3. URA CHOROPLETH REGIONS
    # ==========================================
    ura_group = folium.FeatureGroup(name="Regional Boundaries (Choropleth)", show=True)
    boxes_group = folium.FeatureGroup(name="Regional Data Boxes", show=True)

    ura_colors = {
        "NORTH REGION": "#4fc3f7",     # Light Blue
        "NORTH-EAST REGION": "#4fc3f7",# Merged into North conceptually for coloring
        "EAST REGION": "#fde047",      # Yellow
        "WEST REGION": "#86efac",      # Green
        "CENTRAL REGION": "#f9a8d4"    # Pink
    }

    # Fetch URA Regions via local file
    print("[*] Plotting URA Regions...")
    ura_data = None
    if os.path.exists("ura_regions.json"):
        try:
            with open("ura_regions.json", "r", encoding="utf-8") as f:
                ura_data = json.load(f)
        except Exception as e:
            print(f"[!] Error loading local ura_regions.json: {e}")
    else:
        # Fallback to web request
        try:
            url = "https://raw.githubusercontent.com/itsray01/acerexpansion/main/ura_regions.json"
            res = requests.get(url)
            if res.status_code == 200:
                ura_data = res.json()
        except: pass

    if ura_data:
        for feature in ura_data['features']:
            region_name = feature['properties']['REGION_N']
            # Default to Central if undefined
            fill_color = ura_colors.get(region_name, "#f9a8d4")
            
            folium.GeoJson(
                feature,
                style_function=lambda x, color=fill_color: {
                    'fillColor': color,
                    'color': '#ffffff',
                    'weight': 1.5,
                    'fillOpacity': 0.35
                },
                tooltip=region_name.title()
            ).add_to(ura_group)
            
        # Draw Data Callout Boxes manually for the 4 regions
        regions_centers = {
            "North": (1.43, 103.81),
            "West": (1.35, 103.71),
            "East": (1.35, 103.95),
            "Central": (1.29, 103.83)
        }
        
        for r_name, (r_lat, r_lon) in regions_centers.items():
            # Placeholder calculations - can be wired to actual data loops
            box_html = f"""
            <div style="background: white; border: 1px solid #ccc; padding: 10px; border-radius: 6px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 140px;">
                <h4 style="margin:0 0 5px 0; font-family: Arial; font-size:14px; color:#333;">{r_name} Region</h4>
                <div style="font-family: Arial; font-size:11px; color:#666;">
                    Branches: <b>5</b><br>
                    Tracked Sch: <b>78</b><br>
                    Untapped: <b>21</b>
                </div>
            </div>
            """
            folium.Marker(
                location=[r_lat, r_lon],
                icon=folium.DivIcon(html=box_html, icon_anchor=(70, 40))
            ).add_to(boxes_group)

    # ==========================================
    # 4. PLOT SCHOOLS (With strict coordinates)
    # ==========================================
    print("[*] Plotting Schools...")
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True)
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True)
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True)
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True)

    heat_data = []

    for school in schools_data:
        lat = school.get("lat")
        lon = school.get("lon")
        name = school.get("name", "Unknown School")
        level = school.get("level", "")

        if not lat or not lon: continue

        # Add to heatmap data
        heat_data.append([lat, lon, 1])

        # Style by Level
        color = "gray"
        radius = 4
        group = None
        
        if "PRIMARY" in level:
            color = "#38bdf8" # Sky blue
            group = primary_group
        elif "SECONDARY" in level:
            color = "#a78bfa" # Violet
            group = secondary_group
        elif "JUNIOR COLLEGE" in level or "MIXED" in level:
            color = "#fbbf24" # Amber
            group = jc_group
        elif "INTERNATIONAL" in level:
            color = "#f43f5e" # Rose Pink
            group = intl_group
            radius = 5 # Make premium schools slightly larger

        if group:
            query = name.replace(" ", "+")
            popup_html = f"""
            <div style="font-family: Arial, sans-serif; min-width: 150px;">
                <b style="color: {color};">{name}</b><br>
                <span style="font-size: 11px; color: #666;">Type: {level.title()}</span><br>
                <a href="https://www.google.com/search?q={query}+Singapore+Official+Website" target="_blank" style="font-size: 11px; text-decoration: none; color: #0b57d0;">[+] Search Web</a>
            </div>
            """
            
            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                popup=folium.Popup(popup_html, max_width=250),
                tooltip=name,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.7,
                weight=1
            ).add_to(group)

    # ==========================================
    # 5. HEATMAP LAYER
    # ==========================================
    heatmap_group = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False)
    if heat_data:
        plugins.HeatMap(
            heat_data,
            radius=20,
            blur=15,
            max_zoom=13, # Locks heatmap intensity so it stays red when zooming in
            gradient={0.2: '#000000', 0.4: '#22d3ee', 0.6: '#facc15', 0.8: '#ef4444', 1.0: '#991b1b'}
        ).add_to(heatmap_group)

    # ==========================================
    # 6. COMPETITOR LAYER (TRIANGLES)
    # ==========================================
    print("[*] Plotting Competitor Database...")
    comp_group = folium.FeatureGroup(name="Competitor Network", show=False)
    
    competitors = []
    if os.path.exists("competitor_db.json"):
        try:
            with open("competitor_db.json", "r", encoding="utf-8") as f:
                competitors = json.load(f)
        except Exception as e: print(f"Competitor load error: {e}")
        
    for comp in competitors:
        lat = comp.get("lat")
        lon = comp.get("lon")
        if not lat or not lon: continue
        
        brand = comp.get("brand", "Competitor")
        # Base shadow and default color
        comp_color = "#333333"
        
        if "Kumon" in brand: comp_color = "#1B365D" # Dark Blue
        elif "Mind Stretcher" in brand: comp_color = "#F2D2A9" # Light Gold
        elif "Zenith" in brand: comp_color = "#808080" # Gray
        elif "Learning Lab" in brand or "TLL" in brand: comp_color = "#A28E5C" # Muted Gold
        elif "Aspire" in brand: comp_color = "#4A90E2" # Blue

        # Draw Triangle using DivIcon
        triangle_html = f"""
        <div style="
            width: 0; 
            height: 0; 
            border-left: 8px solid transparent;
            border-right: 8px solid transparent;
            border-bottom: 14px solid {comp_color};
            filter: drop-shadow(0px 2px 2px rgba(0,0,0,0.5));
        "></div>
        """
        
        folium.Marker(
            location=[lat, lon],
            popup=f"<b>{brand}</b><br>{comp.get('branch', '')}",
            tooltip=f"Competitor: {brand}",
            icon=folium.DivIcon(html=triangle_html, icon_anchor=(8, 14))
        ).add_to(comp_group)

    # ==========================================
    # 7. BTO MEGA-ESTATES (RADAR PULSE)
    # ==========================================
    print("[*] Plotting BTO Mega-Estates...")
    bto_group = folium.FeatureGroup(name="Upcoming BTO Estates (2026-2030)", show=True)
    
    # 6 Massive upcoming population hubs
    mega_btos = [
        {"name": "Tengah Mega Town", "lat": 1.3644, "lon": 103.7306, "desc": "42,000 homes. Major smart city."},
        {"name": "Bayshore Precinct", "lat": 1.3142, "lon": 103.9431, "desc": "10,000 homes along East Coast."},
        {"name": "Chencharu (Yishun)", "lat": 1.4116, "lon": 103.8273, "desc": "10,000 homes in new Yishun estate."},
        {"name": "Woodlands North", "lat": 1.4452, "lon": 103.7846, "desc": "10,000 homes near RTS Link."},
        {"name": "Mount Pleasant", "lat": 1.3283, "lon": 103.8378, "desc": "5,000 premium homes in Central."},
        {"name": "Ulu Pandan", "lat": 1.3175, "lon": 103.7744, "desc": "3,000 homes in mature Dover/Clementi."}
    ]
    
    for bto in mega_btos:
        # Custom CSS for pulsing radar effect
        icon_html = """
        <div style="
            background-color: #ef4444;
            width: 14px;
            height: 14px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 0 10px #ef4444, 0 0 20px #ef4444;
            animation: pulse-red 2s infinite;
        "></div>
        <style>
            @keyframes pulse-red {
                0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
                70% { box-shadow: 0 0 0 15px rgba(239, 68, 68, 0); }
                100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
            }
        </style>
        """
        
        folium.Marker(
            location=[bto["lat"], bto["lon"]],
            popup=f"<b style='color:#ef4444;'>{bto['name']}</b><br>{bto['desc']}",
            tooltip=f"Mega BTO: {bto['name']}",
            icon=folium.DivIcon(html=icon_html, icon_anchor=(7, 7))
        ).add_to(bto_group)

    # ==========================================
    # 8. LIVE HDB TENDERS (GLOWING GREEN BEACONS)
    # ==========================================
    print("[*] Plotting Live HDB Tenders...")
    tenders_group = folium.FeatureGroup(name="Live HDB Tenders (Actionable)", show=True)
    
    live_tenders = []
    if os.path.exists("live_tenders.json"):
        try:
            with open("live_tenders.json", "r", encoding="utf-8") as f:
                live_tenders = json.load(f)
        except Exception as e: print(f"Error reading local live_tenders.json: {e}")
    else:
        try:
            res = requests.get("https://raw.githubusercontent.com/itsray01/acerexpansion/main/live_tenders.json", timeout=10)
            if res.status_code == 200: live_tenders = res.json()
        except: pass

    if live_tenders:
        for tender in live_tenders:
            try:
                lat = tender.get("lat")
                lon = tender.get("lon")
                if not lat or not lon: continue
                
                # Make it pop with custom HTML Green Beacon
                icon_html = """
                <div style="
                    background-color: #10B981;
                    width: 16px;
                    height: 16px;
                    border-radius: 50%;
                    border: 2px solid white;
                    box-shadow: 0 0 10px #10B981, 0 0 20px #10B981;
                    animation: pulse-green 2s infinite;
                "></div>
                <style>
                    @keyframes pulse-green {
                        0% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
                        70% { box-shadow: 0 0 0 10px rgba(16, 185, 129, 0); }
                        100% { box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
                    }
                </style>
                """
                
                popup_html = f"""
                <div style="font-family: Arial, sans-serif; width: 220px;">
                    <h4 style="margin: 0 0 5px 0; color: #10B981;">🟢 LIVE TENDER</h4>
                    <b style="font-size: 14px;">{tender.get('project', 'Unknown')}</b><br>
                    <span style="color: #666; font-size: 12px;">{tender.get('address', '')}</span>
                    <hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
                    <b>Rent:</b> {tender.get('price', 'N/A')}<br>
                    <b>Size:</b> {tender.get('size_sqft', 'N/A')} sqft<br>
                    <b>PSF:</b> ${tender.get('psf', 'N/A')}<br>
                    <hr style="margin: 8px 0; border: 0; border-top: 1px solid #eee;">
                    <a href="{tender.get('url', 'https://place2lease.hdb.gov.sg/')}" target="_blank" style="color: #0b57d0; text-decoration: none; font-weight: bold;">[+] View on HDB Place2Lease</a>
                </div>
                """
                
                folium.Marker(
                    location=[lat, lon],
                    popup=folium.Popup(popup_html, max_width=250),
                    tooltip="🟢 Live HDB Tender",
                    icon=folium.DivIcon(html=icon_html, icon_anchor=(8, 8))
                ).add_to(tenders_group)
            except Exception as e:
                print(f"Error mapping tender: {e}")

    # ==========================================
    # 9. PLOT ACER BRANCHES & CATCHMENT
    # ==========================================
    print("[*] Plotting Acer Academy Branches...")
    branch_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)

    for name, coords in EXISTING_BRANCHES.items():
        # Inner Core Icon
        folium.CircleMarker(
            location=coords,
            radius=6,
            popup=f"<b>Acer Academy {name}</b>",
            tooltip=f"Acer Academy {name}",
            color="white",
            weight=2,
            fill=True,
            fill_color="#0b57d0",
            fill_opacity=1.0,
            zIndexOffset=1000
        ).add_to(branch_group)

        # 1.5km Catchment Ring
        folium.Circle(
            location=coords,
            radius=1500,
            color="#0b57d0",
            weight=1,
            fill=True,
            fill_color="#0b57d0",
            fill_opacity=0.1
        ).add_to(branch_group)

    # ==========================================
    # 10. INTERACTIVE EXPANSION SIMULATOR
    # ==========================================
    sim_group = folium.FeatureGroup(name="Simulate Expansion (Click Map)", show=False)
    
    click_js = """
    function onMapClick(e) {
        if (!window.simLayerActive) return;
        
        if (window.simMarker) {
            map.removeLayer(window.simMarker);
            map.removeLayer(window.simCircle);
        }
        
        window.simMarker = L.circleMarker(e.latlng, {
            radius: 8,
            color: 'white',
            weight: 2,
            fillColor: '#facc15',
            fillOpacity: 1.0
        }).addTo(map);
        
        window.simCircle = L.circle(e.latlng, {
            radius: 1500,
            color: '#facc15',
            weight: 2,
            fillColor: '#facc15',
            fillOpacity: 0.2
        }).addTo(map);
        
        window.simMarker.bindPopup("<b>Simulated Branch</b><br>1.5km Radius").openPopup();
    }
    
    map.on('click', onMapClick);
    
    map.on('overlayadd', function(e) {
        if (e.name === 'Simulate Expansion (Click Map)') window.simLayerActive = true;
    });
    map.on('overlayremove', function(e) {
        if (e.name === 'Simulate Expansion (Click Map)') {
            window.simLayerActive = false;
            if (window.simMarker) {
                map.removeLayer(window.simMarker);
                map.removeLayer(window.simCircle);
            }
        }
    });
    """
    m.get_root().script.add_child(folium.Element(click_js))
    sim_group.add_to(m)

    # ==========================================
    # 11. REORDER LAYERS FOR CLEAN MENU
    # ==========================================
    # The order you add them here defines the order in the top-right menu!
    branch_group.add_to(m)
    tenders_group.add_to(m)
    comp_group.add_to(m)
    bto_group.add_to(m)
    primary_group.add_to(m)
    secondary_group.add_to(m)
    jc_group.add_to(m)
    intl_group.add_to(m)
    heatmap_group.add_to(m)
    ura_group.add_to(m)
    boxes_group.add_to(m)

    # ==========================================
    # 12. ADD LAYER CONTROL & LEGEND
    # ==========================================
    folium.LayerControl(collapsed=False).add_to(m)

    # Upgraded Legend with Competitor Triangles
    legend_html = '''
    <div style="
        position: fixed; 
        bottom: 20px; left: 20px; width: 220px;
        background-color: rgba(255, 255, 255, 0.95);
        border: 1px solid #e0e0e0; border-radius: 8px;
        padding: 15px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        font-family: 'Segoe UI', Arial, sans-serif; font-size: 12px; z-index: 9999;">
        <h4 style="margin: 0 0 10px 0; font-size: 13px; color: #333;">Map Legend</h4>
        
        <i class="fa fa-circle" style="color: #0b57d0; margin-right: 5px;"></i> Acer Branch (1.5km Zone)<br>
        <i class="fa fa-circle" style="color: #10B981; margin-right: 5px; text-shadow: 0 0 5px #10B981;"></i> <b>Live HDB Tender</b><br>
        <i class="fa fa-bullseye" style="color: #ef4444; margin-right: 5px; text-shadow: 0 0 5px #ef4444;"></i> Upcoming BTO Estate<br>
        
        <div style="margin-top: 8px; margin-bottom: 5px; font-weight: bold; color: #555;">Competitors</div>
        <i class="fa fa-caret-up" style="color: #1B365D; font-size: 16px; margin-right: 5px;"></i> Kumon<br>
        <i class="fa fa-caret-up" style="color: #F2D2A9; font-size: 16px; margin-right: 5px;"></i> Mind Stretcher<br>
        <i class="fa fa-caret-up" style="color: #808080; font-size: 16px; margin-right: 5px;"></i> Zenith<br>
        <i class="fa fa-caret-up" style="color: #A28E5C; font-size: 16px; margin-right: 5px;"></i> The Learning Lab<br>
        <i class="fa fa-caret-up" style="color: #4A90E2; font-size: 16px; margin-right: 5px;"></i> Aspire Hub<br>
        
        <div style="margin-top: 8px; margin-bottom: 5px; font-weight: bold; color: #555;">Schools</div>
        <i class="fa fa-circle" style="color: #38bdf8; margin-right: 5px;"></i> Primary<br>
        <i class="fa fa-circle" style="color: #a78bfa; margin-right: 5px;"></i> Secondary<br>
        <i class="fa fa-circle" style="color: #fbbf24; margin-right: 5px;"></i> Junior College<br>
        <i class="fa fa-circle" style="color: #f43f5e; margin-right: 5px;"></i> International
    </div>
    '''
    m.get_root().html.add_child(folium.Element(legend_html))

    print("[*] Saving highly interactive HTML map...")
    m.save("acer_expansion_map.html")
    print("[SUCCESS] Map successfully updated and saved to 'acer_expansion_map.html'")

if __name__ == "__main__":
    generate_map()
