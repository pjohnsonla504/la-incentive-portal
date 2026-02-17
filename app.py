import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import numpy as np
from pathlib import Path

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Default Louisiana Center & Zoom for a full statewide view
LA_CENTER = {"lat": 30.9, "lon": -91.8}
LA_ZOOM = 6.2

# --- 1. GLOBAL STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    /* Global Background and Font */
    html, body, [class*="stApp"] { 
        font-family: 'Inter', sans-serif !important; 
        background-color: #0b0f19 !important; 
        color: #ffffff; 
    }
    
    /* SECTION STYLING */
    .content-section { padding: 50px 0; border-bottom: 1px solid #1e293b; }
    .section-num { font-size: 0.85rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.2em; text-transform: uppercase; }
    .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; letter-spacing: -0.02em; }
    .narrative-text { color: #94a3b8; font-size: 1.1rem; line-height: 1.6; max-width: 800px; margin-bottom: 30px; }
    
    /* BENEFIT CARDS */
    .benefit-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 30px; }
    .benefit-card { 
        background-color: #111827 !important; 
        padding: 30px; 
        border: 1px solid #1e293b; 
        border-radius: 12px; 
    }
    .benefit-card h3 { color: #4ade80; font-size: 1.25rem; margin-bottom: 12px; font-weight: 700; }
    .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }

    /* SECTION 5 FILTER TITLES (WHITE FONT) */
    div[data-testid="stWidgetLabel"] p {
        color: white !important;
        font-weight: 600 !important;
        font-size: 1.1rem !important;
    }

    /* ANCHOR ASSET UI */
    .anchor-scroll-container { height: 450px; overflow-y: auto; padding-right: 10px; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; background: #0f172a; }
    .anchor-ui-box { background: #1f2937; border: 1px solid #374151; padding: 15px; border-radius: 10px; margin-bottom: 12px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=3600)
def load_assets():
    this_dir = Path(__file__).parent
    # Standardizing GeoJSON name based on your repository listing
    gj_path = this_dir / "tl_2025_22_tract.json"
    master_path = this_dir / "Opportunity Zones 2.0 - Master Data File.csv"
    anchors_path = this_dir / "la_anchors.csv"

    def smart_read_csv(path):
        for enc in ['utf-8', 'latin1', 'cp1252']:
            try: return pd.read_csv(path, encoding=enc)
            except: continue
        return pd.read_csv(path)

    master = smart_read_csv(master_path)
    anchors = smart_read_csv(anchors_path)
    with open(gj_path, "r") as f:
        gj = json.load(f)

    # Standardize GEOID and Eligibility
    master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
    master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
        lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
    )
    
    centers = {}
    for feature in gj['features']:
        geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
        try:
            geom = feature['geometry']
            coords = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
            centers[geoid] = [np.mean(coords[:, 1]), np.mean(coords[:, 0])]
        except: continue
    return gj, master, anchors, centers

gj, master_df, anchors_df, tract_centers = load_assets()

# --- SECTION 1: OVERVIEW ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>Section 01</div>
    <div class='section-title'>Portal Overview</div>
    <div class='narrative-text'>
        The Louisiana Opportunity Zones 2.0 Portal is a strategic decision-support tool designed to identify 
        and advocate for census tracts with the highest potential for community impact and economic growth. 
        By aligning federal tax incentives with local anchor assets, this platform provides a data-driven 
        roadmap for the next generation of Louisiana investment.
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 2: BENEFIT FRAMEWORK ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>Section 02</div>
    <div class='section-title'>Benefit Framework</div>
    <div class='narrative-text'>Opportunity Zones offer three primary federal income tax benefits for qualified investments:</div>
    <div class='benefit-grid'>
        <div class='benefit-card'>
            <h3>Tax Deferral</h3>
            <p>Investors can defer federal taxes on prior capital gains until December 31, 2026, if those gains are reinvested in a Qualified Opportunity Fund.</p>
        </div>
        <div class='benefit-card'>
            <h3>Basis Step-Up</h3>
            <p>A 5-year hold increases the basis by 10%. A 7-year hold increases it by 15%, effectively reducing the taxable gain.</p>
        </div>
        <div class='benefit-card'>
            <h3>Permanent Exclusion</h3>
            <p>After a 10-year holding period, investors pay $0 in federal capital gains tax on any appreciation of their OZ investment.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 3: TRACT ADVOCACY ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>Section 03</div>
    <div class='section-title'>Tract Advocacy</div>
    <div class='narrative-text'>
        Advocating for "Opportunity Zone 2.0" status requires demonstrating both economic need and investment readiness. 
        Our selection criteria focuses on tracts that bridge the gap between historic disinvestment and future industrial or residential viability.
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 4: BEST PRACTICES ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>Section 04</div>
    <div class='section-title'>Best Practices</div>
    <div class='narrative-text'>Successful OZ projects leverage public-private partnerships and local community engagement.</div>
    <div class='benefit-grid'>
        <div class='benefit-card'>
            <h3>Community Alignment</h3>
            <p>Ensure projects meet local needs such as workforce housing, grocery access, or high-speed internet infrastructure.</p>
        </div>
        <div class='benefit-card'>
            <h3>Capital Stack Integration</h3>
            <p>Combine OZ equity with New Markets Tax Credits (NMTC), Low-Income Housing Tax Credits (LIHTC), or state-level incentives.</p>
        </div>
        <div class='benefit-card'>
            <h3>Impact Reporting</h3>
            <p>Track metrics like jobs created, minority-owned business support, and environmental remediation to maintain stakeholder support.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 5: COMMAND CENTER ---
st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>Section 05</div><div class='section-title'>Strategic Analysis Command Center</div>", unsafe_allow_html=True)

# Filter titles now styled to white via CSS above
col_f1, col_f2 = st.columns(2)
with col_f1:
    selected_region = st.selectbox("Select Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
with col_f2:
    filtered_by_reg = master_df[master_df['Region'] == selected_region] if selected_region != "All Louisiana" else master_df
    selected_parish = st.selectbox("Select Parish", ["All in Region"] + sorted(filtered_by_reg['Parish'].dropna().unique().tolist()))

# Final Filtered Data
display_df = filtered_by_reg.copy()
if selected_parish != "All in Region":
    display_df = display_df[display_df['Parish'] == selected_parish]

# DYNAMIC VIEW LOGIC
is_filtered = (selected_region != "All Louisiana" or selected_parish != "All in Region")
map_center = LA_CENTER
map_zoom = LA_ZOOM

if is_filtered and not display_df.empty:
    relevant_geoids = display_df['geoid_str'].tolist()
    coords = [tract_centers[g] for g in relevant_geoids if g in tract_centers]
    if coords:
        map_center = {"lat": np.mean([c[0] for c in coords]), "lon": np.mean([c[1] for c in coords])}
        map_zoom = 9.2 if selected_parish != "All in Region" else 7.8

# Map Rendering
fig = px.choropleth_mapbox(
    display_df,
    geojson=gj,
    locations="geoid_str",
    featureidkey="properties.GEOID",
    color="Eligibility_Status",
    color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
    mapbox_style="carto-darkmatter",
    center=map_center,
    zoom=map_zoom,
    opacity=0.8,
    hover_data=["Parish", "Region"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=700, paper_bgcolor='rgba(0,0,0,0)')
st.plotly_chart(fig, use_container_width=True)

# Anchor Assets Row
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("📍 Selection-Specific Anchor Assets")
anchor_html = "<div class='anchor-scroll-container'>"
visible_anchors = anchors_df[anchors_df['Parish'].isin(display_df['Parish'].unique())] if is_filtered else anchors_df

for _, row in visible_anchors.iterrows():
    anchor_html += f"""
    <div class='anchor-ui-box'>
        <b style='color:#4ade80;'>{row.get('Anchor_Type', 'Asset')}</b><br>
        <span style='font-size:1.1rem; font-weight:700;'>{row.get('Anchor_Name', 'Unknown')}</span><br>
        <small style='color:#94a3b8;'>Parish: {row.get('Parish', 'N/A')}</small>
    </div>
    """
anchor_html += "</div>"
st.markdown(anchor_html, unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)