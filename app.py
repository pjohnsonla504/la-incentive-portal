import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import numpy as np

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Default Louisiana Center & Zoom
LA_CENTER = {"lat": 30.9, "lon": -91.8}
LA_ZOOM = 6.5

# --- 1. GLOBAL STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; }
    .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 160px; }
    .benefit-card h3 { color: #4ade80; font-size: 1.2rem; margin-bottom: 10px; }
    .benefit-card p { color: #94a3b8; font-size: 0.95rem; }
    
    /* Fixed Scrollable Anchor Container */
    .anchor-scroll-container { height: 420px; overflow-y: auto; padding-right: 8px; border: 1px solid #1e293b; border-radius: 8px; padding: 15px; background: #0b0f19; }
    .anchor-ui-box { background: #1f2937; border: 1px solid #374151; padding: 12px; border-radius: 8px; margin-bottom: 10px; }
    .anchor-link { color: #4ade80 !important; text-decoration: none; font-size: 0.75rem; font-weight: 700; display: inline-block; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE (WITH ENCODING FIX) ---
@st.cache_data(ttl=3600)
def load_assets():
    base_path = os.path.dirname(__file__)
    gj_path = os.path.join(base_path, "louisiana_tracts.json")
    master_path = os.path.join(base_path, "Opportunity Zones 2.0 - Master Data File.csv")
    anchors_path = os.path.join(base_path, "la_anchors.csv")

    def smart_read_csv(path):
        # Fallback encoding strategy to fix UnicodeDecodeError
        for enc in ['utf-8', 'latin1', 'cp1252']:
            try: return pd.read_csv(path, encoding=enc)
            except UnicodeDecodeError: continue
        return pd.read_csv(path)

    # Load Files
    master = smart_read_csv(master_path)
    anchors = smart_read_csv(anchors_path)
    
    with open(gj_path, "r") as f:
        gj = json.load(f)

    # Process GEOIDs for mapping
    master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
    master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
        lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
    )
    
    # Calculate tract centers for zoom logic
    centers = {}
    for feature in gj['features']:
        geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
        try:
            geom = feature['geometry']
            coords = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
            centers[geoid] = [np.mean(coords[:, 1]), np.mean(coords[:, 0])] # [Lat, Lon]
        except: continue
        
    return gj, master, anchors, centers

gj, master_df, anchors_df, tract_centers = load_assets()

# --- 3. SECTIONS 1-4 ---
st.markdown("<div class='content-section'><div class='section-num'>01</div><div class='section-title'>Portal Overview</div><p style='color:#94a3b8;'>Strategic intelligence for identifying census tracts eligible for Opportunity Zones 2.0 across the State of Louisiana.</p></div>", unsafe_allow_html=True)

st.markdown("<div class='content-section'><div class='section-num'>02</div><div class='section-title'>Benefit Framework</div>", unsafe_allow_html=True)
c2 = st.columns(3)
c2[0].markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Reinvested gains are deferred until the 2026 tax year.</p></div>", unsafe_allow_html=True)
c2[1].markdown("<div class='benefit-card'><h3>Step-Up in Basis</h3><p>10% increase for 5-year holds; 15% for 7-year holds.</p></div>", unsafe_allow_html=True)
c2[2].markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Zero tax on appreciation for investments held over 10 years.</p></div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# (Sections 3 & 4 follow same pattern...)
st.markdown("<div class='content-section'><div class='section-num'>03</div><div class='section-title'>Tract Advocacy</div>", unsafe_allow_html=True)
st.markdown("<div class='content-section'><div class='section-num'>04</div><div class='section-title'>Best Practices</div></div>", unsafe_allow_html=True)

# --- 4. SECTION 5: COMMAND CENTER ---
st.markdown("<div class='content-section'><div class='section-num'>05</div><div class='section-title'>Strategic Analysis Command Center</div>", unsafe_allow_html=True)

f1, f2 = st.columns(2)
with f1: 
    selected_region = st.selectbox("Filter by Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
filtered_df = master_df.copy()
if selected_region != "All Louisiana":
    filtered_df = filtered_df[filtered_df['Region'] == selected_region]

with f2:
    selected_parish = st.selectbox("Filter by Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
if selected_parish != "All in Region":
    filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]

# --- DYNAMIC MAP ZOOM LOGIC ---
is_filtered = (selected_region != "All Louisiana" or selected_parish != "All in Region")
map_center = LA_CENTER
map_zoom = LA_ZOOM

if is_filtered and not filtered_df.empty:
    relevant_geoids = filtered_df['geoid_str'].tolist()
    coords = [tract_centers[g] for g in relevant_geoids if g in tract_centers]
    if coords:
        avg_lat = np.mean([c[0] for c in coords])
        avg_lon = np.mean([c[1] for c in coords])
        map_center = {"lat": avg_lat, "lon": avg_lon}
        map_zoom = 9.0 if selected_parish != "All in Region" else 7.8

# Map Rendering
fig = px.choropleth_mapbox(
    filtered_df,
    geojson=gj,
    locations="geoid_str",
    featureidkey="properties.GEOID",
    color="Eligibility_Status",
    color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#334155"},
    mapbox_style="carto-darkmatter",
    center=map_center,
    zoom=map_zoom,
    opacity=0.7
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600, paper_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)

# --- ANCHOR ASSET SCROLLABLE LIST ---
st.subheader("📍 Local Anchor Assets")
anchor_html = "<div class='anchor-scroll-container'>"
# Only show assets related to filtered parishes
visible_anchors = anchors_df[anchors_df['Parish'].isin(filtered_df['Parish'].unique())] if is_filtered else anchors_df

for _, row in visible_anchors.iterrows():
    link = row.get('Link', '#')
    anchor_html += f"""
    <div class='anchor-ui-box'>
        <b style='color:#4ade80;'>{row.get('Type', 'Asset')}</b><br>
        {row.get('Name', 'Unknown')}<br>
        <small>{row.get('Parish', '')}</small><br>
        <a href='{link}' class='anchor-link' target='_blank'>VIEW ASSET ↗</a>
    </div>
    """
anchor_html += "</div>"
st.markdown(anchor_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)