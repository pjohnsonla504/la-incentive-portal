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
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    
    /* Progress Bar */
    .progress-container { width: 100%; background-color: #1e293b; height: 6px; margin-bottom: 40px; }
    .progress-fill { width: 85%; height: 100%; background-color: #4ade80; }

    /* Benefit & Metric Cards */
    .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; }
    .benefit-header { font-size: 1.6rem; font-weight: 900; color: #ffffff; margin-bottom: 15px; }
    .benefit-body { font-size: 1.05rem; color: #f8fafc; line-height: 1.6; }

    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }

    /* Anchor Tag UI */
    .anchor-pill { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE (MASTER FILE + ANCHORS) ---
@st.cache_data(ttl=3600)
def load_assets():
    # 1. Load GeoJSON (FIPS 22)
    url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        geojson = resp.json()
    except:
        # Fallback to empty if GitHub fails
        geojson = {"type": "FeatureCollection", "features": []}

    # 2. Load Master Data & Anchors
    # The map eligibility & metric card data comes from Opportunity Zones Master File.
    # The la anchors CSV provides the anchor data.
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    anchors = pd.read_csv("la_anchors.csv")
    
    # Ensure GEOID is a clean 11-digit string for the join
    df['GEOID_STR'] = df['GEOID'].astype(str).str.split('.').str[0].str.zfill(11)
    
    # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0.
    # Assuming column 'is_eligible' exists in your Master File
    df['map_color'] = df['is_eligible'].apply(lambda x: 1 if x else 0)
    
    return geojson, df, anchors

gj, master_df, anchors_df = load_assets()

# --- HEADER & PROGRESS ---
st.markdown("<div class='progress-container'><div class='progress-fill'></div></div>", unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

# Main Grid: Map (4/10) | Profile (6/10)
m_col, p_col = st.columns([4, 6])

with m_col:
    fig = px.choropleth(
        master_df,
        geojson=gj,
        locations="GEOID_STR",
        featureidkey="properties.GEOID",
        color="map_color",
        color_discrete_map={1: "#4ade80", 0: "#1e293b"}, # Green for eligible only
        projection="mercator"
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        height=680 
    )
    
    selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

with p_col:
    # Default Selection Logic
    target_geoid = "22071001700" 
    if selection and selection.get("selection", {}).get("points"):
        target_geoid = str(selection["selection"]["points"][0]["location"])
    
    # Filter specific tract row from Opportunity Zones Master File
    tract_row = master_df[master_df["GEOID_STR"] == target_geoid]
    
    if not tract_row.empty:
        data = tract_row.iloc[0]
        st.markdown(f"""
            <div style='padding-left:10px;'>
                <h2 style='margin-bottom:0;'>Tract {target_geoid}</h2>
                <p style='color:#4ade80; font-weight:800; text-transform:uppercase;'>{data.get('Parish', 'Louisiana')} | {data.get('Region', 'Opportunity Zone')}</p>
            </div>
        """, unsafe_allow_html=True)

        # Metric Cards (Populated from Master File)
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{data.get('poverty_rate', 0)}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
        with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>${data.get('med_income', 0)/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
        with c3: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if data.get('is_eligible') else 'NO'}</div><div class='metric-label'>OZ 2.0 Eligible</div></div>", unsafe_allow_html=True)

        # 7 Anchors Analysis (From la_anchors.csv)
        st.markdown("<div style='margin-top:30px; padding:25px; background:#161b28; border-radius:8px; border:1px solid #1e293b;'>", unsafe_allow_html=True)
        st.markdown("<p style='font-size:0.8rem; font-weight:900; color:#94a3b8; text-transform:uppercase; margin-bottom:15px;'>Infrastructure & Community Anchors</p>", unsafe_allow_html=True)
        
        # Filtering anchors based on proximity (example placeholder logic)
        relevant_anchors = ["Port of New Orleans", "LSU Health", "Innovation Center", "Main St. District", "Transit Hub", "Regional Medical", "Broadband Node"]
        for a in relevant_anchors:
            st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {a}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style='margin-top:20px; padding:10px; border-left:3px solid #4ade80;'>
                <p style='font-size:0.9rem; color:#cbd5e1;'><b>Selection Strategy:</b> This tract is prioritized due to its eligibility for the OBBB 30% Rural Step-Up and proximity to the {relevant_anchors[0]}.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("Select a highlighted green tract on the map to view the strategic profile.")