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
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }
    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
    .narrative-text { font-size: 1.1rem; line-height: 1.6; color: #cbd5e1; margin-bottom: 25px; max-width: 1100px; }
    
    /* Progress Bar */
    .progress-bar { width: 100%; background: #1e293b; height: 6px; margin-bottom: 40px; }
    .progress-fill { width: 95%; height: 100%; background: #4ade80; }

    /* Benefit Cards */
    .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; transition: all 0.3s ease; }
    .benefit-header { font-size: 1.6rem; font-weight: 900; color: #ffffff; margin-bottom: 15px; }
    .benefit-body { font-size: 1.05rem; color: #f8fafc; line-height: 1.6; }

    /* Metric Cards */
    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.6rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }

    /* Anchor Pills */
    .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 3956 * 2 * asin(sqrt(a))

@st.cache_data(ttl=3600)
def load_assets():
    # Load GeoJSON from GitHub (Louisiana FIPS 22)
    url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    try: geojson = requests.get(url, timeout=10).json()
    except: geojson = {"type": "FeatureCollection", "features": []}

    # Load CSVs with specific fallback encodings for Unicode issues
    def read_csv_safe(file):
        for enc in ['utf-8', 'latin1', 'cp1252']:
            try: return pd.read_csv(file, encoding=enc)
            except: continue
        return pd.DataFrame()

    master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
    anchors = read_csv_safe("la_anchors.csv")
    
    # Process Master File for Map Join
    if not master.empty:
        # Fuzzy match 11-digit FIPCode header
        fip_col = [c for c in master.columns if 'fipcode' in c.lower() or 'geography' in c.lower()][0]
        master['geoid_str'] = master[fip_col].astype(str).str.replace('.0', '', regex=False).str.zfill(11)
        
        # Tracks highlighted green are only those eligible for Opportunity Zone 2.0
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).lower() in ['eligible', 'yes', '1'] else 0)

    # Pre-calculate Tract Centroids for Anchor Proximity
    centroids = {}
    for feature in geojson['features']:
        coords = np.array(feature['geometry']['coordinates'][0])
        if coords.ndim == 3: coords = coords[0] # Poly vs MultiPoly
        centroids[feature['properties']['GEOID']] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
        
    return geojson, master, anchors, centroids

gj, master_df, anchors_df, tract_centers = load_assets()

# --- HEADER & PROGRESS ---
st.markdown("<div class='progress-bar'><div class='progress-fill'></div></div>", unsafe_allow_html=True)

# --- SECTION 1 & 2 (Narrative Content) ---
st.markdown("<div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Recommendation Portal</div>", unsafe_allow_html=True)
st.markdown("<div class='narrative-text'>Drive private investment into distressed communities through OBBB 2025 incentives.</div>", unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

m_col, p_col = st.columns([4, 6])

with m_col:
    # Interactive Map sourcing from Master File + GitHub JSON
    fig = px.choropleth(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                        color="map_color", color_discrete_map={1: "#4ade80", 0: "#1e293b"}, projection="mercator")
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650)
    selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

with p_col:
    # Tract Selection Logic
    target_geoid = "22071001700" # Default (Orleans)
    if selection and selection.get("selection", {}).get("points"):
        target_geoid = str(selection["selection"]["points"][0]["location"])
    
    row = master_df[master_df["geoid_str"] == target_geoid]
    
    if not row.empty:
        d = row.iloc[0]
        st.markdown(f"<h2>Tract {target_geoid}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#4ade80; font-weight:bold;'>{d.get('Parish', 'Louisiana').upper()} | {d.get('Region', 'ZONE')}</p>", unsafe_allow_html=True)

        # Metric Cards using Master File exact headers
        c1, c2, c3 = st.columns(3)
        with c1:
            pov_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
            st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get(pov_col, 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
        with c2:
            inc_col = 'Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)'
            st.markdown(f"<div class='metric-card'><div class='metric-value'>${d.get(inc_col, 0)/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='metric-card'><div class='metric-value'>{'ELIGIBLE' if d['map_color']==1 else 'INELIGIBLE'}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

        # 7 Anchors Logic from la_anchors.csv
        st.markdown("<p style='text-transform:uppercase; font-size:0.8rem; margin-top:30px; font-weight:bold; color:#94a3b8;'>Strategic Proximity Anchors</p>", unsafe_allow_html=True)
        if not anchors_df.empty and target_geoid in tract_centers:
            t_lon, t_lat = tract_centers[target_geoid]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(7).iterrows():
                st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {a['Name']} <span style='font-weight:400; color:#94a3b8;'>• {a['dist']:.1f} mi</span></div>", unsafe_allow_html=True)
    else:
        st.info("Select a highlighted green tract to view profile data.")