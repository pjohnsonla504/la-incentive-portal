import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM (SHRUNK FOR 100% VIEW) ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    
    /* Text Blurbs */
    .intro-box { background: white; padding: 15px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 10px; }
    .best-practice { background: #fefce8; padding: 10px; border-left: 4px solid #facc15; font-size: 0.85rem; margin-bottom: 10px; color: #854d0e; }
    
    /* Progress & Header */
    .stat-pill { background: #1e293b; color: #4ade80; padding: 2px 12px; border-radius: 15px; font-weight: 800; font-size: 0.8rem; }
    .profile-header { background-color: #1e293b; padding: 12px; border-radius: 8px; border-left: 6px solid #22c55e; margin-bottom: 15px; color: white; }
    .header-item { display: inline-block; margin-right: 20px; }
    .header-label { color: #94a3b8; font-size: 0.7rem; text-transform: uppercase; display: block; }
    .header-value { color: #ffffff; font-size: 1rem; font-weight: 700; }

    /* Shrunk Metrics */
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.2rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #cbd5e1 !important; font-size: 0.75rem !important; text-transform: uppercase; }
    [data-testid="stMetric"] { background-color: #334155; border-radius: 8px; padding: 10px !important; border: 1px solid #475569; }
    
    /* Indicators */
    .indicator-box { border-radius: 8px; padding: 8px; text-align: center; margin-bottom: 8px; border: 1px solid #e2e8f0; height: 65px; display: flex; flex-direction: column; justify-content: center; background: white; }
    .status-yes { background-color: #dcfce7; border-color: #22c55e !important; color: #166534; }
    .status-no { background-color: #f1f5f9; border-color: #cbd5e1 !important; opacity: 0.6; color: #64748b; }
    .indicator-label { font-size: 0.65rem; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 0.9rem; font-weight: 900; }
    
    .section-label { color: #475569; font-size: 0.75rem; font-weight: 800; margin-top: 10px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; text-transform: uppercase; }
    .stProgress > div > div > div > div { background-color: #22c55e; height: 8px; }
    
    /* Anchors Table */
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.75rem; background: white; }
    .anchor-table td { padding: 6px; border-bottom: 1px solid #f1f5f9; }
    .anchor-table th { text-align: left; color: #64748b; font-size: 0.65rem; padding: 6px; background: #f8fafc; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA LOAD ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    BASE_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
    def find_col(keywords):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keywords): return col
        return None

    cols = {
        "unemp": find_col(['unemployment', 'rate']),
        "metro": find_col(['metro', 'status']),
        "hs": find_col(['hs', 'degree']) or find_col(['high', 'school']),
        "bach": find_col(['bachelor']),
        "labor": find_col(['labor', 'force']),
        "home": find_col(['median', 'home', 'value']),
        "pov": POV_COL, "base": BASE_COL
    }

    # GEOID Prep
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # Logic
    df['is_nmtc'] = df[POV_COL].apply(clean) >= 20.0
    df['is_deeply'] = (df[POV_COL].apply(clean) > 40.0) | (df[cols['unemp']].apply(clean) >= 10.5)

    # MAP FILTER - Identify only eligible tracts based on file
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y'])
    
    # Map Z value: 1 for green, 0 for light grey background
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

    # Assets & GeoJSON
    a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        gid = str(feat['properties'].get('GEOID', '')).zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        if 'INTPTLAT' in feat['properties']:
            centers[gid] = {"lat": float(str(feat['properties']['INTPTLAT']).replace('+','')), "lon": float(str(feat['properties']['INTPTLON']).replace('+',''))}

    return df, gj, a, centers, cols

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

# --- 3. SESSION STATE ---
if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

# --- 4. INTRO BLURBS ---
st.markdown("""
<div class='intro-box'>
    <h4 style='margin:0; color:#1e293b;'>Introduction</h4>
    <p style='font-size:0.85rem; margin:5px 0;'>Welcome to the <b>Louisiana Opportunity Zone 2.0 Strategic Portal</b>. This tool is designed to identify and nominate high-impact census tracts for the 2026 American Dynamism initiative. Our focus is on aligning federal tax incentives with local economic assets to catalyze growth in distressed communities.</p>
    <h5 style='margin:10px 0 5px 0; font-size:0.8rem; color:#475569;'>Directions</h5>
    <ul style='font-size:0.8rem; margin:0; padding-left:20px;'>
        <li><b>Identify:</b> Eligible tracts are highlighted in <b>Green</b> on the map.</li>
        <li><b>Analyze:</b> Click a green tract to view its economic profile and proximity to strategic anchors (ports, universities, etc.).</li>
        <li><b>Nominate:</b> Use the action panel to commit a tract to the 150-site portfolio target.</li>
    </ul>
</div>
""", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
col_map, col_side = st.columns([0.5, 0.5])

with col_map:
    # High-contrast map
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(200,200,200,0.1)"], [1, "rgba(34, 197, 94, 0.85)"]],
        showscale=False, marker_line_width=0.5, marker_line_color="#475569"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 30.8, "lon": -91.8}, zoom=6.0),
        height=650, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="v66_map")
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        st.rerun()

with col_side:
    st.markdown("<div class='best-practice'><b>Best Practice:</b> Prioritize tracts that qualify as 'Deeply Distressed' and are within 10 miles of a Port or Research University to maximize ROI potential.</div>", unsafe_allow_html=True)
    
    st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center;'><b>PORTFOLIO PROGRESS</b> <span class='stat-pill'>{st.session_state.recom_count} / 150</span></div>", unsafe_allow_html=True)
    st.progress(min(st.session_state.recom_count / 150, 1.0))

    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"""
            <div class='profile-header'>
                <div class='header-item'><span class='header-label'>Tract ID</span><span class='header-value'>{sid}</span></div>
                <div class='header-item'><span class='header-label'>Parish</span><span class='header-value'>{row.get('Parish')}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # INDICATORS
        m1, m2, m3, m4 = st.columns(4)
        m_val = str(row.get(cols['metro'], '')).lower()
        with m1: st.markdown(f"<div class='indicator-box {'status-yes' if 'metro' in m_val else 'status-no'}'><div class='indicator-label'>Urban</div><div class='indicator-value'>{'YES' if 'metro' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='indicator-box {'status-yes' if 'rural' in m_val else 'status-no'}'><div class='indicator-label'>Rural</div><div class='indicator-value'>{'YES' if 'rural' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc'] else 'status-no'}'><div class='