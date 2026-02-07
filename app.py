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
    
    /* Benefit & Metric Cards */
    .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; transition: all 0.3s ease; }
    .benefit-header { font-size: 1.6rem; font-weight: 900; color: #ffffff; margin-bottom: 15px; }
    .benefit-body { font-size: 1.05rem; color: #f8fafc; line-height: 1.6; }
    
    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.6rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }
    
    .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    .anchor-dist { color: #94a3b8; font-weight: 400; margin-left: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. UTILITIES & DATA ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 3956 * 2 * asin(sqrt(a)) # Miles

@st.cache_data(ttl=3600)
def load_assets():
    # Load GeoJSON
    url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    try: geojson = requests.get(url, timeout=10).json()
    except: geojson = {"type": "FeatureCollection", "features": []}

    # Load CSVs with specific headers
    master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv", encoding='latin1').apply(lambda x: x.str.strip() if x.dtype == "object" else x)
    anchors = pd.read_csv("la_anchors.csv", encoding='latin1')
    
    # Pre-process Master File
    master['geoid_str'] = master['11-digit FIPCode'].astype(str).str.zfill(11)
    master['map_color'] = master['Opportunity Zones Insiders Eligibilty'].apply(
        lambda x: 1 if str(x).lower() in ['eligible', 'yes', '1', 'true'] else 0
    )
    
    # Extract Tract Centroids from GeoJSON for distance calculation
    centroids = {}
    for feature in geojson['features']:
        coords = np.array(feature['geometry']['coordinates'][0])
        if coords.ndim == 3: coords = coords[0] # Handle MultiPolygon
        centroids[feature['properties']['GEOID']] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
        
    return geojson, master, anchors, centroids

gj, master_df, anchors_df, tract_centers = load_assets()

# --- SECTION 2: FRAMEWORK ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Louisiana OZ 2.0 Framework</div></div>", unsafe_allow_html=True)
b1, b2, b3 = st.columns(3)
with b1:
    st.markdown("<div class='benefit-card'><div class='benefit-header'>Permanent Deferral</div><div class='benefit-body'>Investors can defer taxes on original capital gains through the new 2025 permanent window.</div></div>", unsafe_allow_html=True)
with b2:
    st.markdown("<div class='benefit-card'><div class='benefit-header'>30% Rural Step-Up</div><div class='benefit-body'>Qualified Rural Funds receive an enhanced basis step-up, excluding 30% of the original gain.</div></div>", unsafe_allow_html=True)
with b3:
    st.markdown("<div class='benefit-card'><div class='benefit-header'>Zero Appreciation Tax</div><div class='benefit-body'>Hold for 10 years to eliminate all federal capital gains tax on the new OZ investment.</div></div>", unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("<div class='content-section' style='margin-top:40px;'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

m_col, p_col = st.columns([4, 6])

with m_col:
    fig = px.choropleth(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                        color="map_color", color_discrete_map={1: "#4ade80", 0: "#1e293b"}, projection="mercator")
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=700)
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

        # Metrics
        c1, c2, c3 = st.columns(3)
        with c1: 
            pov = d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 'N/A')
            st.markdown(f"<div class='metric-card'><div class='metric-value'>{pov}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
        with c2: 
            inc = d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)
            st.markdown(f"<div class='metric-card'><div class='metric-value'>${inc/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
        with c3: 
            status = "ELIGIBLE" if d.get('map_color') == 1 else "INELIGIBLE"
            st.markdown(f"<div class='metric-card'><div class='metric-value' style='font-size:1.1rem;'>{status}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

        # --- 7 Anchors Proximity Logic ---
        st.markdown("<p style='text-transform:uppercase; font-size:0.8rem; margin-top:25px; font-weight:bold; color:#94a3b8;'>Nearest Strategic Anchors</p>", unsafe_allow_html=True)
        
        if not anchors_df.empty and target_geoid in tract_centers:
            t_lon, t_lat = tract_centers[target_geoid]
            # Calculate distance to all anchors
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            # Take Top 7
            nearest = anchors_df.sort_values('dist').head(7)
            
            for _, anchor in nearest.iterrows():
                st.markdown(f"""
                    <div class='anchor-pill anchor-hit'>
                        ✔ {anchor['Name']} 
                        <span class='anchor-dist'>• {anchor['Type']} • {anchor['dist']:.1f} mi</span>
                    </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Select a tract on the map to analyze anchor proximity.")