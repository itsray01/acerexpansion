# ... existing code ...
                    if lat == 0 or lon == 0: continue
                    
                    name = row_lower.get('name') or row_lower.get('school_name') or "Unknown"
                    level = row_lower.get('education_level') or row_lower.get('level') or row_lower.get('mainlevel_code') or "PRIMARY"
                    address = row_lower.get('address') or row_lower.get('postal_address') or "Address Not Provided"
                    region = row_lower.get('region') or ""
                    
                    schools.append({
                        "name": row.get('name') or row.get('School_Name') or name.title(),
                        "lat": lat,
                        "lon": lon,
                        "level": level.upper(),
                        "address": row.get('address') or row.get('Address') or address.title(),
                        "region": region
                    })
                except Exception as e:
                    continue
# ... existing code ...
```

### 2. Set Executive Layers to Hidden on Default Load
```python:Master Map Generator:generate_map.py
# ... existing code ...
            # Increased opacity from 0.35 to 0.65 to ensure colors pop against the new dark_matter map
            return { 'fillColor': color, 'color': color, 'weight': 1.5, 'fillOpacity': 0.65 }
        
        with open(URA_GEOJSON_PATH, 'r') as f:
            geo_data = json.load(f)
        folium.GeoJson(geo_data, name="Regional Boundaries (Choropleth)", show=False, style_function=style_function).add_to(m)

    # Calculate Regional Metrics for the Infographic Boxes
# ... existing code ...
```

```python:Master Map Generator:generate_map.py
# ... existing code ...
    # ==========================================
    # INFOGRAPHIC OCEAN BOXES & LEADER LINES
    # ==========================================
    infographic_group = folium.FeatureGroup(name="Regional Data Boxes", show=False)
    for region, config in REGIONS_CONFIG.items():
        color, anchor, center = config["color"], config["anchor"], config["center"]
# ... existing code ...
```

### 3. Clean Up the Forceful CSS
```python:Master Map Generator:generate_map.py
# ... existing code ...
    .region-label { position: relative !important; z-index: 9999 !important; font-family: 'Montserrat', sans-serif !important; font-size: 13px !important; text-transform: uppercase !important; letter-spacing: 3.5px !important; white-space: nowrap !important; pointer-events: none !important; transform: translate(-50%, -50%) !important; transition: all 0.2s ease !important; }
    
    /* ====================================================
       DYNAMIC LAYER HIDING (THE MAGIC TRICK)
       ==================================================== */
    /* Hide the 1.5km rings in Exec mode since they share a checkbox with the branch pins */
    .exec-mode-active path.coverage-ring {
        display: none !important;
    }
    
    /* Sidebar CSS */
    #sidebar-backdrop { position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.5); z-index: 99998; opacity: 0; pointer-events: none; transition: opacity 0.3s; }
# ... existing code ...
```

### 4. Build the New Popup Tooltips
```python:Master Map Generator:generate_map.py
# ... existing code ...
    for school in schools:
        level = school.get("level", "").upper()
        lat, lon, name = school["lat"], school["lon"], school["name"]
        address = school.get("address", "Address Not Provided")
        
        is_covered = any(haversine(lat, lon, b_lat, b_lon) <= 1500 for b_lat, b_lon in EXISTING_BRANCHES.values())
        if not is_covered:
            potential_expansion_coords.append([lat, lon])
        
        if "PRIMARY" in level: fill_color, group, cat = "#38BDF8", primary_group, "PRIMARY"
        elif "SECONDARY" in level: fill_color, group, cat = "#A78BFA", secondary_group, "SECONDARY"
        elif "JUNIOR COLLEGE" in level: fill_color, group, cat = "#FBBF24", jc_group, "JUNIOR COLLEGE"
        elif "INTERNATIONAL" in level: fill_color, group, cat = "#F472B6", intl_group, "INTERNATIONAL"
        else: continue
        
        schools_dir[cat].append(name)
        
        # Inject custom className "school-dot" to allow CSS to hide it during Exec Clean mode
        folium.CircleMarker(
            location=[lat, lon], 
            radius=7, 
            popup=f"<div style='min-width: 180px;'><b style='color: {fill_color}; font-size: 14px;'>{name}</b><br><span style='color: #FFD700; font-weight: 600;'>{level.title()}</span><br><span style='font-size: 12px; color: #AAAAAA;'>📍 {address}</span></div>",
            tooltip=f"<span style='font-size: 14px;'>{name}</span>", 
            color="white", weight=1, fill_color=fill_color, fill=True, fill_opacity=0.85,
            className="school-dot"
        ).add_to(group)
        
    for grp in [primary_group, secondary_group, jc_group, intl_group]: grp.add_to(m)
# ... existing code ...
```

### 5. Inject the Smart UI Toggle JavaScript
```python:Master Map Generator:generate_map.py
# ... existing code ...
            simLayer.addLayer(circle);
        }, true);

        map.on('baselayerchange', function(e) {
            var legend = document.getElementById('legend-box'), sidePanel = document.getElementById('side-panel'), title = legend ? legend.querySelector('h4') : null;
            var innerRing = document.getElementById('legend-ring-inner'), innerRingSim = document.getElementById('legend-ring-inner-sim'), spans = legend ? legend.querySelectorAll('span.legend-text') : [], regionLabels = document.querySelectorAll('.region-label');
            var isExecDark = (e.name === 'Executive Dark Canvas (Clean)');
            var isDark = (e.name === 'Dark Streets (Default)');
            
            // --- SMART LAYER AUTO-TOGGLE ---
            var execEnable = ['Regional Boundaries (Choropleth)', 'Regional Data Boxes'];
            var execDisable = ['Primary Schools', 'Secondary Schools', 'Junior Colleges', 'International Schools', 'Town & Region Labels', 'Expansion Heatmap'];

            document.querySelectorAll('.leaflet-control-layers-overlays label').forEach(function(label) {
                var cb = label.querySelector('input[type="checkbox"]');
                if (!cb) return;
                var text = label.textContent.trim();
                
                if (isExecDark) {
                    if (execEnable.some(l => text.includes(l)) && !cb.checked) cb.click();
                    if (execDisable.some(l => text.includes(l)) && cb.checked) cb.click();
                } else {
                    if (execEnable.some(l => text.includes(l)) && cb.checked) cb.click();
                    if (execDisable.some(l => text.includes(l)) && !cb.checked) cb.click();
                }
            });

            if (isExecDark) {
                mapContainer.classList.add('exec-mode-active');
                if (legend) legend.style.display = 'none';
# ... existing code ...
