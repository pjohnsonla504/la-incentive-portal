import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import requests

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    
    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }

    .anchor-pill { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE (FIXED ENCODING) ---
@st.cache_data(ttl=3600)
def load_assets():
    # 1. Load GeoJSON
    url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    try:
        geojson = requests.get(url, timeout=10).json()
    except:
        geojson = {"type": "FeatureCollection", "features": []}

    # 2. Load Master & Anchors with fallback encodings
    # Attempting common encodings to solve the UnicodeDecodeError
    def read_csv_safe(file_path):
        for enc in ['utf-8', 'latin1', 'cp1252', 'utf-8-sig']:
            try:
                return pd.read_csv(file_path, encoding=enc)
            except UnicodeDecodeError:
                continue
        return pd.read_csv(file_path) # Last resort

    df = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
    anchors = read_csv_safe("la_anchors.csv")
    
    # Process for join
    df['GEOID_STR'] = df['GEOID'].astype(str).str.split('.').str[0].str.zfill(11)
    # Highlight green if eligible
    df['map_color'] = df['is_eligible'].map({True: 1, False: 0})
    
    return geojson, df, anchors

gj, master_df, anchors_df = load_assets()

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

m_col, p_col = st.columns([4, 6])

with m_col:
    fig = px.choropleth(
        master_df,
        geojson=gj,
        locations="GEOID_STR",
        featureidkey="properties.GEOID",
        color="map_color",
        color_discrete_map={1: "#4ade80", 0: "#1e293b"},
        projection="mercator"
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650)
    selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

with p_col:
    target_geoid = "22071001700" 
    if selection and selection.get("selection", {}).get("points"):
        target_geoid = str(selection["selection"]["points"][0]["location"])
    
    tract_row = master_df[master_df["GEOID_STR"] == target_geoid]
    
    if not tract_row.empty:
        data = tract_row.iloc[0]
        st.markdown(f"<h2>Tract {target_geoid}</h2>", unsafe_allow_html=True)

        # Metric Cards from Master File
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{data.get('poverty_rate', 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>${data.get('med_income', 0)/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
        with c3: 
            status = "Eligible" if data.get('is_eligible') else "Ineligible"
            st.markdown(f"<div class='metric-card'><div class='metric-value'>{status}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

        # Anchors from la_anchors.csv
        st.markdown("<p style='text-transform:uppercase; font-size:0.8rem; margin-top:20px;'>Local Anchor Assets</p>", unsafe_allow_html=True)
        # Display up to 7 anchors (mocking a proximity filter for now)
        sample_anchors = anchors_df.head(7)['Anchor Name'].tolist() if not anchors_df.empty else ["No Data"]
        for a in sample_anchors:
            st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {a}</div>", unsafe_allow_html=True)
    else:
        st.info("Select a tract to view details.")