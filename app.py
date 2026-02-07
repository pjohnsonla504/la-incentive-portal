import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: 700; font-size: 1rem !important; }
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.8rem !important; font-weight: 800; }
    .stMetric { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 15px; }
    .indicator-box { border-radius: 8px; padding: 18px; text-align: center; margin-bottom: 15px; border: 1px solid #475569; }
    .status-yes { background-color: rgba(74, 222, 128, 0.25); border-color: #4ade80; }
    .status-no { background-color: #1e293b; border-color: #334155; opacity: 0.5; }
    .indicator-label { font-size: 0.95rem; color: #ffffff; text-transform: uppercase; font-weight: 800; margin-bottom: 5px; }
    .indicator-value { font-size: 1.4rem; font-weight: 900; color: #ffffff; }
    .stMarkdown p, .stMarkdown li { font-size: 1.1rem !important; line-height: 1.6; }
    h3 { font-size: 1.8rem !important; font-weight: 800 !important; }
    .counter-pill { background: #4ade80; color: #0f172a; padding: 10px 25px; border-radius: 30px; font-weight: 900; font-size: 1.1rem; }
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 1rem; margin-top: 15px; }
    .anchor-table th { text-align: left; color: #cbd5e1; border-bottom: 2px solid #4ade80; padding: 12px; }
    .anchor-table td { padding: 12px; border-bottom: 1px solid #334155; color: #f1f5f9; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA LOAD ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    try:
        a = pd.read_csv("la_anchors.csv")
    except:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    df['is_eligible'] = df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y'])
    df['map_status'] = np.where(df['is_eligible'], 1, 0)

    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        lat, lon = p.get('INTPTLAT'), p.get('INTPTLON')
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}
    return df, gj, a, centers

master_df, la_geojson, anchor_df, tract_centers = load_data()

# --- 3. SESSION ---
if "recom_count" not in st.session_state:
    st.session_state.recom_count = 0
if "selected_tract" not in st.session_state:
    st.session_state.selected_tract = None

# --- 4. TOP BAR ---
t1, t2 = st.columns([0.7, 0.3])
with t1:
    st.title("Strategic Portal: Louisiana")
with t2:
    st.markdown(f"<div style='text-align:right; margin-top:20px;'><span class='counter-pill'>RECOMMENDATIONS: {st.session_state.recom_count}</span></div>", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    fig = go.Figure()
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(200,200,200,0.1)"], [1, "rgba(74, 222, 128, 0.65)"]],
        showscale=False, marker_line_width=1, marker_line_color="#1e293b"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 31.0, "lon": -91.8}, zoom=6.2),
        height=950, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="oz_map")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)

with col_side:
    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"<h3 style='color:#4ade80;'>TRACT: {sid}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#94a3b8;'>PARISH: {row.get('Parish')} | REGION: {row.get('Region', 'LA')}</p>", unsafe_allow_html=True)