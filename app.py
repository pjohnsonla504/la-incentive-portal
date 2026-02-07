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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; margin: 0 auto; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }
    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
    .narrative-text { font-size: 1.1rem; line-height: 1.6; color: #cbd5e1; margin-bottom: 25px; max-width: 1100px; }
    .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; transition: all 0.3s ease; }
    .section-progress-container { width: 100%; background-color: #1e293b; height: 8px; margin: 20px 0 40px 0; border-radius: 4px; overflow: hidden; }
    .section-progress-fill { width: 100%; height: 100%; background: linear-gradient(90deg, #4ade80, #22c55e); }
    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.6rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }
    .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA UTILITIES ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 3956 * 2 * asin(sqrt(a))

@st.cache_data(ttl=3600)
def load_assets():
    # Load Louisiana Census Tracts (FIPS 22)
    # Using a secondary reliable raw source
    url = "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
    # Note: For tracts, we'll stick to the arcee123 source but add a fallback
    url_tracts = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    
    try:
        r = requests.get(url_tracts, timeout=10)
        geojson = r.json()
    except:
        geojson = {"type": "FeatureCollection", "features": []}

    def read_csv_safe(path):
        for enc in ['utf-8', 'latin1', 'cp1252', 'utf-8-sig']:
            try: 
                df = pd.read_csv(path, encoding=enc)
                df.columns = df.columns.str.strip()
                return df
            except: continue
        return pd.DataFrame()

    master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
    anchors = read_csv_safe("la_anchors.csv")
    
    if not master.empty:
        # Search for FIPCode column aggressively
        fip_candidates = [c for c in master.columns if '11-digit' in c or 'fipcode' in c.lower()]
        if fip_candidates:
            # Clean scientific notation if it exists (e.g. 2.2E+10)
            master['geoid_str'] = master[fip_candidates[0]].apply(lambda x: format(int(float(x)), 'd') if pd.notnull(x) else "")
            master['geoid_str'] = master['geoid_str'].str.zfill(11)
        
        # Green Logic
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        if elig_col in master.columns:
            master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).lower() in ['eligible', 'yes', '1'] else 0)
        else:
            master['map_color'] = 0

    # Centroids
    centroids = {}
    if geojson.get('features'):
        for feature in geojson['features']:
            geoid = feature['properties'].get('GEOID')
            geom = feature.get('geometry', {})
            if geom['type'] == 'Polygon':
                coords = np.array(geom['coordinates'][0])
                centroids[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            elif geom['type'] == 'MultiPolygon':
                coords = np.array(geom['coordinates'][0][0])
                centroids[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
        
    return geojson, master, anchors, centroids

gj, master_df, anchors_df, tract_centers = load_assets()

# --- SECTIONS 1, 2, 3 ---
st.markdown("<div class='content-section' style='padding-top:80px;'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Recommendation Portal</div><div class='narrative-text'>The Opportunity Zones program...</div></div>", unsafe_allow_html=True)

# (Sections 2 and 3 kept exactly the same as your script...)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("""
<div class='content-section' style='margin-top:40px;'>
    <div class='section-num'>SECTION 4</div>
    <div class='section-title'>Strategic Selection Tool</div>
    <div class='narrative-text'>
        Identify high-conviction zones by selecting green eligible tracts. The profile panel below will load specific socio-economic indicators and local anchor proximity.
    </div>
    <div class='section-progress-container'>
        <div class='section-progress-fill'></div>
    </div>
</div>
""", unsafe_allow_html=True)

if master_df.empty or not gj.get('features'):
    st.error("⚠️ Map Data Error: Could not find Census GeoJSON or Master Data File. Please check your filenames.")
else:
    m_col, p_col = st.columns([5, 5])
    
    with m_col:
        # THE MAP RENDER
        fig = px.choropleth(
            master_df,
            geojson=gj,
            locations="geoid_str",
            featureidkey="properties.GEOID",
            color="map_color",
            color_discrete_map={1: "#4ade80", 0: "#1e293b"},
            projection="mercator"
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0},
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            height=700,
            dragmode="pan"
        )
        selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

    with p_col:
        # Selection Logic
        target_geoid = "22071001700" 
        if selection and selection.get("selection", {}).get("points"):
            target_geoid = str(selection["selection"]["points"][0]["location"])
        
        row = master_df[master_df["geoid_str"] == target_geoid]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<h2>Tract {target_geoid}</h2>", unsafe_allow_html=True)
            st.markdown(f"<p style='color:#4ade80; font-weight:800;'>{d.get('Parish', 'LOUISIANA').upper()} PARISH</p>", unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            with c1:
                pov = d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 'N/A')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{pov}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            with c2:
                inc = d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>${inc/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
            with c3:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if d['map_color']==1 else 'NO'}</div><div class='metric-label'>Eligible</div></div>", unsafe_allow_html=True)

            st.markdown("<p style='text-transform:uppercase; font-size:0.8rem; margin-top:30px; font-weight:bold; color:#94a3b8;'>Nearest Strategic Anchors</p>", unsafe_allow_html=True)
            if not anchors_df.empty and target_geoid in tract_centers:
                t_lon, t_lat = tract_centers[target_geoid]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                for _, a in anchors_df.sort_values('dist').head(7).iterrows():
                    st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {a['Name']} <span style='font-weight:400; color:#94a3b8;'>• {a['dist']:.1f} mi</span></div>", unsafe_allow_html=True)