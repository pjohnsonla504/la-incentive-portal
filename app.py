import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import requests
from math import radians, cos, sin, asin, sqrt

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    
    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.6rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }
    
    .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    .anchor-dist { color: #94a3b8; font-weight: 400; margin-left: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. UTILITIES ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 3956 * 2 * asin(sqrt(a))

# --- 3. DATA ENGINE (FUZZY HEADER MATCHING) ---
@st.cache_data(ttl=3600)
def load_assets():
    # Load GeoJSON
    url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    try: geojson = requests.get(url, timeout=10).json()
    except: geojson = {"type": "FeatureCollection", "features": []}

    # Load CSVs
    def read_csv_robust(path):
        for enc in ['utf-8', 'latin1', 'cp1252', 'utf-8-sig']:
            try: return pd.read_csv(path, encoding=enc)
            except: continue
        return pd.DataFrame()

    master = read_csv_robust("Opportunity Zones 2.0 - Master Data File.csv")
    anchors = read_csv_robust("la_anchors.csv")
    
    if not master.empty:
        # Fuzzy match for FIPCode column
        fip_col = [c for c in master.columns if 'fipcode' in c.lower() or 'geography' in c.lower()][0]
        master['geoid_str'] = master[fip_col].astype(str).str.replace('.0', '', regex=False).str.zfill(11)
        
        # Fuzzy match for Eligibility (Green Tracks)
        elig_col = [c for c in master.columns if 'insiders' in c.lower() or 'eligibilty' in c.lower()][-1]
        master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).lower() in ['eligible', 'yes', '1'] else 0)
        
    # Extract Centroids
    centroids = {}
    for feature in geojson['features']:
        coords = np.array(feature['geometry']['coordinates'][0])
        if coords.ndim == 3: coords = coords[0]
        centroids[feature['properties']['GEOID']] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
        
    return geojson, master, anchors, centroids

gj, master_df, anchors_df, tract_centers = load_assets()

# --- UI RENDER ---
st.markdown("<div style='width: 100%; background-color: #1e293b; height: 6px; margin-bottom: 40px;'><div style='width: 95%; height: 100%; background-color: #4ade80;'></div></div>", unsafe_allow_html=True)
st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

m_col, p_col = st.columns([4, 6])

with m_col:
    fig = px.choropleth(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                        color="map_color", color_discrete_map={1: "#4ade80", 0: "#1e293b"}, projection="mercator")
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650)
    selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

with p_col:
    target_geoid = "22071001700" 
    if selection and selection.get("selection", {}).get("points"):
        target_geoid = str(selection["selection"]["points"][0]["location"])
    
    row = master_df[master_df["geoid_str"] == target_geoid]
    
    if not row.empty:
        d = row.iloc[0]
        st.markdown(f"<h2>Tract {target_geoid}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#4ade80; font-weight:bold;'>{d.get('Parish', 'LOUISIANA').upper()} | {d.get('Region', 'ZONE')}</p>", unsafe_allow_html=True)

        c1, c2, c3 = st.columns(3)
        with c1:
            pov_col = [c for c in master_df.columns if 'percent below poverty' in c.lower()][0]
            st.markdown(f"<div class='metric-card'><div class='metric-value'>{d[pov_col]}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
        with c2:
            inc_col = [c for c in master_df.columns if 'median family income' in c.lower()][0]
            st.markdown(f"<div class='metric-card'><div class='metric-value'>${d[inc_col]/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if d['map_color']==1 else 'NO'}</div><div class='metric-label'>OZ 2.0 Eligible</div></div>", unsafe_allow_html=True)

        # Nearest Anchors
        st.markdown("<p style='text-transform:uppercase; font-size:0.8rem; margin-top:25px; font-weight:bold; color:#94a3b8;'>7 Strategic Anchors</p>", unsafe_allow_html=True)
        if not anchors_df.empty and target_geoid in tract_centers:
            t_lon, t_lat = tract_centers[target_geoid]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(7).iterrows():
                st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {a['Name']} <span class='anchor-dist'>• {a['Type']} • {a['dist']:.1f} mi</span></div>", unsafe_allow_html=True)