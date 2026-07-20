# ... existing code ...
    .directory-btn:hover { background: rgba(40,40,40,0.95); border-color: #00E5FF; color: #00E5FF; }
    </style>
    """ + f"""
    <div class="acer-dashboard">
        <h4>
            <div style="background-color: transparent; border-radius: 6px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; overflow: hidden; border: 1px solid #fff;">
                <img src="https://i.imgur.com/YhyOq9V.png" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <span>ACER <span style="color:#ff3344;">EXPANSION</span></span>
        </h4>
        <div class="acer-stat">Analyzing <b style="color:#fff;">{len(schools)}</b> educational zones across <b style="color:#fff;">{len(EXISTING_BRANCHES)}</b> active branches.</div>
        <div style="display:flex; justify-content:space-between; font-size:10px; font-weight:700; color:#aaa; margin-top:14px; text-transform:uppercase;">
            <span>Network Status</span><span style="color:#4ADE80;">Total Coverage</span>
        </div>
        <div class="progress-bar-bg"><div class="progress-bar-fill"></div></div>
    </div>
    
    <button class="directory-btn" onclick="alert('Directory view loading...')">📁 DIRECTORY</button>
    """ + """
    <script>
    document.addEventListener("DOMContentLoaded", function() {
# ... existing code ...
```

And right at the very bottom of your script, update the `LayerControl` to be collapsed:

```python:Master Map Generator:generate_map.py
# ... existing code ...
                    regionLabels.forEach(lbl => {
                        lbl.style.color = '#111111';
                        lbl.style.textShadow = '-1px -1px 3px #fff, 1px -1px 3px #fff, -1px 1px 3px #fff, 1px 1px 3px #fff, 0px 0px 15px rgba(255,255,255,0.8)';
                        lbl.style.fontWeight = '800';
                    });
                }
            });
        }
    });
    </script>
    """
    m.get_root().html.add_child(Element(custom_css))

    folium.LayerControl(collapsed=True, position='topright').add_to(m)
    m.save(OUTPUT_MAP_PATH)
    print(f"\n[+] SUCCESS! Interactive map generated: {OUTPUT_MAP_PATH}")

if __name__ == "__main__":
    generate_map()
