import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components
from datetime import datetime

# --- 0. INITIAL CONFIG & STATE ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 
if "search_input" not in st.session_state:
    st.session_state["search_input"] = ""
if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []

def clear_search_func():
    st.session_state["search_input"] = ""

# --- 1. GLOBAL STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
    .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; line-height: 1.1; }
    .hero-subtitle { color: #4ade80; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 5px;}
    .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; margin-bottom: 25px; }
    .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 180px; }
    .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; }
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
    gj = None
    if os.path.exists("tl_2025_22_tract.json"):
        with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
    
    master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
    
    # Eligibility Logic (Strictly OZ 2.0 Eligible = Green)
    master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
        lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
    )
    
    anchors = pd.read_csv("la_anchors.csv")
    centers = {}
    if gj:
        for feature in gj['features']:
            geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
            try:
                coords = np.array(feature['geometry']['coordinates'][0]) if feature['geometry']['type'] == 'Polygon' else np.array(feature['geometry']['coordinates'][0][0])
                centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            except: continue
    return gj, master, anchors, centers

gj, master_df, anchors_df, tract_centers = load_assets()

# --- SECTION 1: HERO ---
st.markdown("""
    <div class='content-section'>
        <div class='section-num'>SECTION 1</div>
        <div class='hero-subtitle'>Strategic Investment</div>
        <div class='hero-title'>Louisiana Opportunity Zone 2.0 Portal</div>
        <div class='narrative-text'>Facilitating long-term private capital to fuel jobs and innovation in Louisiana's most promising census tracts.</div>
    </div>
""", unsafe_allow_html=True)

# --- SECTION 2-4: NARRATIVE BLOCKS ---
sections = [
    ("SECTION 2", "Benefit Framework", "Defer taxes on capital gains and receive basis step-ups for long-term equity investments."),
    ("SECTION 3", "Census Tract Advocacy", "Focusing on rural and deeply distressed areas to ensure equitable economic distribution."),
    ("SECTION 4", "Best Practices", "Leveraging institutional knowledge and local anchors to minimize risk for private investors.")
]

for num, title, text in sections:
    st.markdown(f"<div class='content-section'><div class='section-num'>{num}</div><div class='section-title'>{title}</div><div class='narrative-text'>{text}</div></div>", unsafe_allow_html=True)

# --- SECTION 5: SMART SEARCH & MAP ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Location Intelligence</div></div>", unsafe_allow_html=True)

s_col1, s_col2 = st.columns([0.8, 0.2])
with s_col1:
    search_query = st.text_input("🔍 Search by City, Parish, or Tract ID", key="search_input", placeholder="New Orleans, Baton Rouge, Caddo, or 11-digit FIPS...")
with s_col2:
    st.write(" ")
    st.button("Reset Map", on_click=clear_search_func, use_container_width=True)

# City-to-Parish Mapping Logic
city_to_parish = {
    "new orleans": "orleans", "baton rouge": "east baton rouge", "shreveport": "caddo",
    "metairie": "jefferson", "houma": "terrebonne", "monroe": "ouachita", "alexandria": "rapides"
}

filtered_df = master_df.copy()
if search_query:
    q = search_query.strip().lower()
    target = city_to_parish.get(q, q)
    filtered_df = master_df[(master_df['geoid_str'].str.contains(q)) | (master_df['Parish'].str.lower().str.contains(target))]
    if not filtered_df.empty:
        st.session_state["active_tract"] = str(filtered_df.iloc[0]['geoid_str'])

def render_map(df):
    center = {"lat": 30.8, "lon": -91.8}
    zoom = 6.2
    if len(df) < 500 and not df.empty:
        active_ids = df['geoid_str'].tolist()
        subset = [tract_centers[gid] for gid in active_ids if gid in tract_centers]
        if subset:
            lons, lats = zip(*subset)
            center = {"lat": np.mean(lats), "lon": np.mean(lons)}; zoom = 8.5
    
    fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                               featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                               color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                               mapbox_style="carto-darkmatter", zoom=zoom, center=center, opacity=0.6)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=600)
    return fig

m_col, a_col = st.columns([0.65, 0.35])
with m_col:
    st.plotly_chart(render_map(filtered_df), use_container_width=True)
with a_col:
    st.markdown("**Nearby Anchor Assets**")
    curr_id = st.session_state["active_tract"]
    if curr_id in tract_centers:
        lon, lat = tract_centers[curr_id]
        anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
        for _, a in anchors_df.sort_values('dist').head(8).iterrows():
            st.markdown(f"<div style='background:#111827; border:1px solid #1e293b; padding:10px; border-radius:8px; margin-bottom:8px;'><b>{a['Name']}</b><br><small>{a['Type']} • {a['dist']:.1f} mi</small></div>", unsafe_allow_html=True)

# --- SECTION 6: METRICS ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Metrics</div></div>", unsafe_allow_html=True)
row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
if not row.empty:
    d = row.iloc[0]
    m1, m2, m3, m4 = st.columns(4)
    m1.markdown(f"<div class='metric-card'><div class='metric-value'>{d['Parish']}</div><div class='metric-label'>Parish</div></div>", unsafe_allow_html=True)
    m2.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Eligibility_Status')}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)
    m3.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Designation</div></div>", unsafe_allow_html=True)
    m4.markdown(f"<div class='metric-card'><div class='metric-value'>{st.session_state['active_tract']}</div><div class='metric-label'>FIPS ID</div></div>", unsafe_allow_html=True)