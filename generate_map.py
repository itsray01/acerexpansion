import folium
from folium import plugins
import json
import os
import csv
import random

# ==========================================
# 1. CONFIGURATION & MASTER DATA
# ==========================================
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

REGIONS_TOWNS = {
    "Punggol": (1.4050, 103.9020), "Sengkang": (1.3916, 103.8954), "Tampines": (1.3524, 103.9443),
    "Bedok": (1.3236, 103.9273), "Pasir Ris": (1.3721, 103.9474), "Jurong West": (1.3396, 103.7067),
    "Jurong East": (1.3329, 103.7436), "Clementi": (1.3162, 103.7649), "Bukit Batok": (1.3491, 103.7496),
    "Bukit Panjang": (1.3780, 103.7629), "Choa Chu Kang": (1.3840, 103.7470), "Woodlands": (1.4360, 103.7860),
    "Yishun": (1.4304, 103.8354), "Ang Mo Kio": (1.3691, 103.8454), "Bishan": (1.3526, 103.8352),
    "Toa Payoh": (1.3343, 103.8563), "Hougang": (1.3712, 103.8924), "Serangoon": (1.3554, 103.8679),
    "Bukit Timah": (1.3294, 103.8021), "Queenstown": (1.2942, 103.8062), "Bukit Merah": (1.2819, 103.8239),
    "Geylang": (1.3201, 103.8918), "Kallang": (1.3113, 103.8714), "Sembawang": (1.4491, 103.8185),
    "Novena": (1.3204, 103.8434), "Marine Parade": (1.3020, 103.9046), "Tengah": (1.3700, 103.7000),
    "Changi": (1.3450, 103.9832), "Simei": (1.3429, 103.9531), "Kembangan": (1.3211, 103.9126),
    "MacPherson": (1.3262, 103.8887), "Seletar": (1.4098, 103.8750), "Pioneer": (1.3184, 103.6934),
    "Boon Lay": (1.3385, 103.7058), "Tuas": (1.3294, 103.6397), "West Coast": (1.3030, 103.7661),
    "Telok Blangah": (1.2741, 103.8159), "Sentosa": (1.2494, 103.8303), "Central Area": (1.2789, 103.8536),
    "Orchard": (1.3048, 103.8318), "Newton": (1.3129, 103.8385), "River Valley": (1.2974, 103.8340),
    "Tanglin": (1.3060, 103.8153), "Thomson": (1.3411, 103.8329), "Balestier": (1.3261, 103.8475),
    "Simpang": (1.4420, 103.8490), "Mandai": (1.4241, 103.8052), "Sungei Kadut": (1.4137, 103.7547),
    "Lim Chu Kang": (1.4342, 103.7149), "Bukit Brown": (1.3359, 103.8239), "Marina Bay": (1.2842, 103.8535),
    "Paya Lebar": (1.3182, 103.8936)
}

REGIONS_CONFIG = {
    "North": {"color": "#4A6FA5", "icon": "north_icon.png", "offset": (0, 0.12)},
    "East": {"color": "#E58A35", "icon": "east_icon.png", "offset": (0.1, -0.02)},
    "Central": {"color": "#D33F49", "icon": "central_icon.png", "offset": (-0.08, 0.01)},
    "West": {"color": "#40977B", "icon": "west_icon.png", "offset": (0.01, -0.12)}
}

# ==========================================
# 2. SMART CSV LOADER
# ==========================================
def load_schools_from_csv():
    schools = []
    file_path = "All_Schools_Geocoded.csv"
    
    if not os.path.exists(file_path):
        print(f"[!] Warning: {file_path} not found.")
        return schools
        
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            if not headers: return schools
            
            # Smart Fuzzy Matcher for robust data ingestion
            h_map = {}
            for h in headers:
                h_lower = str(h).strip().lower()
                
                # Strict URL check FIRST to prevent it from stealing the 'address' tag
                if 'url' in h_lower or 'website' in h_lower: 
                    h_map['url'] = h
                elif 'name' in h_lower or 'school' in h_lower:
                    if 'name' not in h_map: h_map['name'] = h
                elif 'lat' in h_lower: 
                    h_map['lat'] = h
                elif 'lon' in h_lower or 'lng' in h_lower: 
                    h_map['lon'] = h
                elif 'level' in h_lower or 'education' in h_lower: 
                    h_map['level'] = h
                elif 'address' in h_lower: 
                    if 'url' not in h_lower and 'website' not in h_lower:
                        h_map['address'] = h
                elif 'region' in h_lower:
                    h_map['region'] = h
                elif 'tier' in h_lower:
                    h_map['tier'] = h
                    
            for row in reader:
                name = row.get(h_map.get('name', ''), '').strip()
                if not name: continue
                
                lat_str = str(row.get(h_map.get('lat', ''), '')).strip()
                lon_str = str(row.get(h_map.get('lon', ''), '')).strip()
                
                # Forcefully sanitize empty blanks preventing the 0 schools crash
                if not lat_str or not lon_str or lat_str == "" or lon_str == "": 
                    continue
                    
                try:
                    # Micro-Jitter Spread for Neighborhoods (Fanning out)
                    lat = float(lat_str) + random.uniform(-0.0015, 0.0015)
                    lon = float(lon_str) + random.uniform(-0.0015, 0.0015)
                except ValueError:
                    continue
                    
                schools.append({
                    "name": name,
                    "lat": lat,
                    "lon": lon,
                    "level": row.get(h_map.get('level', ''), 'Standard').strip(),
                    "address": row.get(h_map.get('address', ''), 'Address N/A').strip(),
                    "url": row.get(h_map.get('url', ''), '').strip(),
                    "region": row.get(h_map.get('region', ''), 'Central').strip().title(),
                    "tier": row.get(h_map.get('tier', ''), 'Standard').strip().title()
                })
                
        print(f"[*] Successfully loaded {len(schools)} schools from CSV.")
    except Exception as e:
        print(f"[!] Error reading CSV: {e}")
        
    return schools

# ==========================================
# 3. MAP GENERATION ENGINE
# ==========================================
def generate_map():
    print("[*] Booting up Master Infographic & Interactive Map Engine...")
    
    # HARD BOUNDARY LOCK - Singapore Coordinates
    # min_zoom=12 ensures it stays tight, and we inject JS rubber-banding later
    m = folium.Map(
        location=[1.3521, 103.8198], 
        zoom_start=12, 
        min_zoom=12,
        tiles=None,
        control_scale=True
    )
    
    # Base Layers
    folium.TileLayer('cartodbdark_matter', name="Dark Streets (Default)").add_to(m)
    folium.TileLayer('cartodbpositron', name="Light Canvas").add_to(m)
    
    # Clean Map Layer (leaves pitch black naturally)
    exec_layer = folium.TileLayer('cartodbdark_matter', name="Executive Dark Canvas (Clean)")
    exec_layer.add_to(m)

    # CSS Injection
    custom_css = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Montserrat:wght@400;600;800&family=Roboto+Mono:wght@400;700&display=swap');
    
    /* Force Leaflet Popups to be Dark Theme */
    .leaflet-popup-content-wrapper {
        background: rgba(20, 20, 24, 0.95) !important;
        border: 1px solid #333 !important;
        color: #FFFFFF !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5) !important;
        backdrop-filter: blur(8px);
    }
    .leaflet-popup-tip {
        background: rgba(20, 20, 24, 0.95) !important;
        border-top: 1px solid #333 !important;
        border-left: 1px solid #333 !important;
    }
    .leaflet-popup-close-button {
        color: #FFFFFF !important;
    }

    body.exec-mode-active .infographic-element {
        display: block !important;
        opacity: 1 !important;
    }
    body:not(.exec-mode-active) .infographic-element {
        display: none !important;
        opacity: 0 !important;
    }
    .region-label {
        font-family: 'Montserrat', sans-serif;
        font-weight: 800;
        font-size: 10px;
        color: #FFFFFF;
        text-shadow: 0px 0px 4px #000000, 0px 0px 8px rgba(0,0,0,0.8);
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    #sidebar-backdrop {
        position: absolute;
        top: 20px;
        right: 20px;
        width: 300px;
        background: rgba(15, 15, 18, 0.85);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        z-index: 1000;
        padding: 20px;
        color: #FFFFFF;
        font-family: 'Montserrat', sans-serif;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    }
    </style>
    """
    m.get_root().html.add_child(folium.Element(custom_css))

    # Feature Groups
    primary_group = folium.FeatureGroup(name="Primary Schools (Sky Blue)", show=True)
    secondary_group = folium.FeatureGroup(name="Secondary Schools (Violet)", show=True)
    jc_group = folium.FeatureGroup(name="Junior Colleges (Amber)", show=True)
    intl_group = folium.FeatureGroup(name="International Schools (Rose Pink)", show=True)
    heatmap_group = folium.FeatureGroup(name="Expansion Heatmap (Untapped)", show=False)
    branches_group = folium.FeatureGroup(name="Acer Academy Branches", show=True)
    towns_group = folium.FeatureGroup(name="Town & Region Labels", show=True)
    infographic_group = folium.FeatureGroup(name="Regional Data Boxes", show=False)

    schools = load_schools_from_csv()
    
    # Regional Data Calculation Counters
    region_stats = {
        "North": {"schools": 0, "students": 0, "branches": 0},
        "West": {"schools": 0, "students": 0, "branches": 0},
        "East": {"schools": 0, "students": 0, "branches": 0},
        "Central": {"schools": 0, "students": 0, "branches": 0}
    }

    potential_expansion_coords = []

    # Map branches to regions 
    for b_name, (b_lat, b_lon) in EXISTING_BRANCHES.items():
        region_key = "Central"
        if "(North)" in b_name: region_key = "North"
        elif "(West)" in b_name: region_key = "West"
        elif "(East)" in b_name: region_key = "East"
        
        region_stats[region_key]["branches"] += 1
        
        folium.Marker(
            location=[b_lat, b_lon],
            icon=folium.Icon(color='red', icon='star', prefix='fa'),
            tooltip=f"<b>{b_name}</b>"
        ).add_to(branches_group)

        folium.Circle(
            location=[b_lat, b_lon],
            radius=1500,
            color='#FF4B4B',
            fill=True,
            fill_color='#FF4B4B',
            fill_opacity=0.1,
            weight=1
        ).add_to(branches_group)

    for school in schools:
        lat, lon = school['lat'], school['lon']
        name = school['name']
        level = school['level']
        address = school['address']
        url = school['url']
        tier = school['tier']
        r_key = school['region']

        if r_key not in region_stats: r_key = "Central"
        
        region_stats[r_key]["schools"] += 1
        if "Primary" in level.title(): region_stats[r_key]["students"] += 1500
        elif "Secondary" in level.title(): region_stats[r_key]["students"] += 1200
        else: region_stats[r_key]["students"] += 1800

        fill_color = '#38BDF8'
        m_group = primary_group
        if 'SECONDARY' in level.upper():
            fill_color = '#A78BFA'
            m_group = secondary_group
        elif 'JUNIOR COLLEGE' in level.upper() or 'MIXED' in level.upper():
            fill_color = '#FBBF24'
            m_group = jc_group
        elif 'INTERNATIONAL' in level.upper():
            fill_color = '#F472B6'
            m_group = intl_group

        url_html = f'<br><br><b style="color: #FFFFFF;">🌐 Web:</b> <a href="{url}" target="_blank" style="color: #38BDF8; text-decoration: underline; font-weight: 600;">Visit Website ↗</a>' if url and str(url).startswith('http') else ''
        
        # Hide Tier if Standard
        tier_html = f'<div style="display: inline-block; background: rgba(255, 215, 0, 0.1); border: 1px solid #FFD700; color: #FFD700; padding: 4px 8px; border-radius: 4px; font-size: 11px; font-weight: 700; letter-spacing: 1px; margin-bottom: 10px;">★ TIER: {tier.upper()}</div>' if tier.lower() != "standard" else ''
        
        popup_html = f"""
        <div style="font-family: 'Montserrat', sans-serif; min-width: 240px; padding: 4px;">
            <div style="font-size: 14px; font-weight: 800; color: {fill_color}; margin-bottom: 6px; text-transform: uppercase; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px;">
                {name}
            </div>
            {tier_html}
            <div style="font-size: 11px; color: #CCCCCC; line-height: 1.6;">
                <b style="color: #FFFFFF;">Level:</b> {level.title()}<br>
                <b style="color: #FFFFFF;">Region:</b> {r_key.title()}<br>
                <b style="color: #FFFFFF;">📍 Addr:</b> {address}{url_html}
            </div>
        </div>
        """
        
        folium.CircleMarker(
            location=[lat, lon],
            radius=6,
            color='#FFFFFF',
            weight=1,
            fill=True,
            fill_color=fill_color,
            fill_opacity=0.9,
            popup=folium.Popup(popup_html, max_width=300)
        ).add_to(m_group)

        # Check coverage for Heatmap
        from math import radians, cos, sin, asin, sqrt
        def haversine(lon1, lat1, lon2, lat2):
            lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
            dlon = lon2 - lon1
            dlat = lat2 - lat1
            a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
            c = 2 * asin(sqrt(a))
            r = 6371000
            return c * r

        is_covered = False
        for b_name, (b_lat, b_lon) in EXISTING_BRANCHES.items():
            if haversine(lon, lat, b_lon, b_lat) <= 1500:
                is_covered = True
                break
        
        if not is_covered:
            potential_expansion_coords.append([lat, lon])

    for grp in [primary_group, secondary_group, jc_group, intl_group]: grp.add_to(m)

    # BOOSTED HEATMAP VIBRANCY
    if potential_expansion_coords:
        plugins.HeatMap(
            potential_expansion_coords, 
            name="Potential Expansion Zones", 
            radius=36, 
            blur=22, 
            min_opacity=0.5, 
            gradient={0.2: '#00C9FF', 0.5: '#A78BFA', 0.8: '#F472B6', 1.0: '#FFD700'}
        ).add_to(heatmap_group)
    heatmap_group.add_to(m)

    # INFOGRAPHIC OCEAN BOXES & LEADER LINES
    for region, config in REGIONS_CONFIG.items():
        base_coords = {
            "North": (1.4360, 103.7860),
            "East": (1.3524, 103.9443),
            "Central": (1.2942, 103.8062),
            "West": (1.3329, 103.7436)
        }
        lat, lon = base_coords[region]
        off_lat, off_lon = config["offset"]
        anchor = (lat + off_lat, lon + off_lon)
        
        stats = region_stats.get(region, {"schools":0, "students":0, "branches":0})
        
        folium.PolyLine(
            locations=[(lat, lon), anchor],
            color=config["color"],
            weight=2,
            dash_array="5, 5",
            opacity=0.6,
            class_name='infographic-element'
        ).add_to(infographic_group)
        
        folium.CircleMarker(
            location=(lat, lon),
            radius=4,
            color=config["color"],
            fill=True,
            fill_opacity=1,
            class_name='infographic-element'
        ).add_to(infographic_group)
        
        box_html = f"""
        <div style="background: rgba(15, 15, 18, 0.95); border: 1px solid {config['color']}; border-radius: 8px; padding: 12px; width: 160px; font-family: 'Montserrat', sans-serif; box-shadow: 0 8px 32px rgba(0,0,0,0.5); backdrop-filter: blur(8px);">
            <div style="color: {config['color']}; font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 4px;">
                ■ {region.upper()}
            </div>
            <table style="width: 100%; font-size: 10px; color: #CCCCCC; font-weight: 600;">
                <tr><td style="padding-bottom: 4px;">Branches:</td><td style="text-align: right; color: #FBBF24;">{stats['branches']}</td></tr>
                <tr><td style="padding-bottom: 4px;">Schools:</td><td style="text-align: right; color: #38BDF8;">{stats['schools']}</td></tr>
                <tr><td style="padding-bottom: 0;">Students:</td><td style="text-align: right; color: #4ADE80;">{stats['students']:,}</td></tr>
            </table>
        </div>
        """
        
        folium.Marker(
            location=anchor, 
            icon=folium.DivIcon(html=box_html, icon_size=(180, 100), icon_anchor=(90, 50), class_name='infographic-element')
        ).add_to(infographic_group)

    infographic_group.add_to(m)

    # 53 Town Labels
    for town, (t_lat, t_lon) in REGIONS_TOWNS.items():
        folium.Marker(
            location=[t_lat, t_lon],
            icon=folium.DivIcon(
                html=f'<div class="region-label">{town.upper()}</div>',
                icon_size=(100, 20),
                icon_anchor=(50, 10)
            )
        ).add_to(towns_group)
    towns_group.add_to(m)
    branches_group.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)

    # Sidebar
    sidebar_html = f"""
    <div id="sidebar-backdrop">
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 20px;">
            <div style="background: #FF4B4B; width: 40px; height: 40px; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 20px;">A</div>
            <div>
                <div style="font-weight: 800; font-size: 16px; letter-spacing: 1px;">ACER ACADEMY</div>
                <div style="color: #FF4B4B; font-size: 10px; font-family: 'Roboto Mono', monospace;">EXPANSION INTELLIGENCE</div>
            </div>
        </div>
        
        <div style="font-size: 11px; color: #A0A0A0; line-height: 1.6; margin-bottom: 20px;">
            Analyzing <b style="color: #FFF;">{len(schools)}</b> educational institutions against <b style="color: #FFF;">{len(EXISTING_BRANCHES)}</b> active branches to identify critical expansion zones.
        </div>
        
        <div style="background: rgba(255,255,255,0.05); border-radius: 6px; padding: 12px; margin-bottom: 12px;">
            <div style="font-size: 10px; color: #888; text-transform: uppercase; margin-bottom: 8px;">Network Status</div>
            <div style="display: flex; justify-content: space-between; font-size: 12px; font-weight: 600;">
                <span>Total Coverage:</span>
                <span style="color: #4ADE80;">{round((len(schools) - len(potential_expansion_coords)) / len(schools) * 100) if schools else 0}%</span>
            </div>
            <div style="width: 100%; background: #333; height: 4px; border-radius: 2px; margin-top: 8px;">
                <div style="width: {round((len(schools) - len(potential_expansion_coords)) / len(schools) * 100) if schools else 0}%; background: #4ADE80; height: 100%; border-radius: 2px;"></div>
            </div>
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(sidebar_html))

    # Boundary Lock & JS Toggle Code
    legend_html = """
    <script>
    document.addEventListener('DOMContentLoaded', function() {
        var map = null;
        for (var key in window) {
            if (key.startsWith('map_') && window[key] instanceof L.Map) {
                map = window[key];
                break;
            }
        }
        
        if (map) {
            // BOUNDARY LOCK: Prevent map from sliding to Malaysia/Indonesia
            var southWest = L.latLng(1.15, 103.55);
            var northEast = L.latLng(1.55, 104.15);
            var bounds = L.latLngBounds(southWest, northEast);
            map.setMaxBounds(bounds);
            map.on('drag', function() {
                map.panInsideBounds(bounds, { animate: false });
            });

            // LOGIC TOGGLE: Smart Checkbox Clicker
            map.on('baselayerchange', function(e) {
                var isExecClean = (e.name === 'Executive Dark Canvas (Clean)');
                var body = document.body;
                
                if (isExecClean) {
                    body.classList.add('exec-mode-active');
                    
                    // Automatically uncheck schools and heatmap
                    document.querySelectorAll('.leaflet-control-layers-selector').forEach(cb => {
                        let label = cb.nextElementSibling ? cb.nextElementSibling.textContent.trim() : cb.parentElement.textContent.trim();
                        if ((label.includes('Schools') || label.includes('Heatmap') || label.includes('Town')) && cb.checked) {
                            cb.click();
                        }
                        if (label.includes('Regional Data Boxes') && !cb.checked) {
                            cb.click();
                        }
                    });
                } else {
                    body.classList.remove('exec-mode-active');
                    
                    // Automatically re-check schools
                    document.querySelectorAll('.leaflet-control-layers-selector').forEach(cb => {
                        let label = cb.nextElementSibling ? cb.nextElementSibling.textContent.trim() : cb.parentElement.textContent.trim();
                        if (label.includes('Schools') && !cb.checked) {
                            cb.click();
                        }
                        if (label.includes('Regional Data Boxes') && cb.checked) {
                            cb.click();
                        }
                    });
                }
            });
        }
    });
    </script>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    m.save("acer_expansion_map.html")
    print("[+] acer_expansion_map.html successfully generated!")

if __name__ == "__main__":
    generate_map()
