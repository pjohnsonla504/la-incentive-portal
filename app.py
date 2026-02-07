import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. THEME & STYLING ---
st.set_page_config(page_title="OZ 2.0 | American Dynamism", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050a14; color: #ffffff; }
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; font-weight: 700 !important; color: #00ff88 !important; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; text-transform: uppercase; color: #94a3b8 !important; }
    .stMetric { background-color: #0f172a; padding: 15px; border-radius: 4px; border: 1px solid #1e293b; }
    .stButton>button { background-color: #00ff88 !important; color: #050a14 !important; font-weight: 700; width: 100%; }
    .anchor-card { background-color: #0f172a; border-left: 3px solid #00ff88; padding: 10px; margin-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"System Link Failure: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None, "selected_anchor": None})

# --- 2. DATA UTILITIES ---
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        p1, p2 = np.radians(float(lat1)), np.radians(float(lat2))
        dp, dl = np.radians(float(lat2)-float(lat1)), np.radians(float(lon2)-float(lon1))
        a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.0

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Load Anchors
    try:
        a = pd.read_csv("la_anchors.csv")
    except UnicodeDecodeError:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    
    a.columns = a.columns.str.strip().str.lower()
    a = a.dropna(subset=['lat', 'lon'])

    # Tract Logic
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    df['map_status'] = np.where(df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 1, 0)

    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        lat, lon = p.get('INTPTLAT'), p.get('INTPTLON')
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}

    m_map = {
        "home": "Median Home Value", "dis": "Disability Population (%)",
        "pop65": "Population 65 years and over", "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)", "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)", "web": "Broadband Internet (%)"
    }
    return df, gj, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTH ---
if not st.session_state["authenticated"]:
    # (Standard login code omitted for brevity but remains the same in your full file)
    st.title("AUTHENTICATE")
    # ... login logic ...
    st.stop()

# --- 4. INTERFACE ---
st.markdown(f"<h2>{st.session_state['a_val']} Strategic Portal</h2>", unsafe_allow_html=True)

# LAYER CONTROL
with st.expander("🛰️ Map Layer Control"):
    show_anchors = st.checkbox("Display Anchor Assets", value=True)
    show_tracts = st.checkbox("Display OZ 2.0 Eligibility", value=True)

col_map, col_side = st.columns([0.6, 0.4])

with col_map:
    fig = go.Figure()
    
    if show_tracts:
        fig.add_trace(go.Choroplethmapbox(
            geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
            featureidkey="properties.GEOID_MATCH",
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0, 255, 136, 0.35)"]],
            showscale=False, marker_line_width=0.3, name="OZ Tracts"
        ))
    
    if show_anchors:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=12, color='#ffffff', symbol='diamond'),
            text=anchor_df['name'], customdata=anchor_df['name'],
            hoverinfo='text', name="Anchors"
        ))
    
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 30.8, "lon": -91.8}, zoom=7),
        height=700, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    
    select_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    # Selection Logic
    if select_data and select_data.get("selection") and select_data["selection"].get("points"):
        point = select_data["selection"]["points"][0]
        if "location" in point: # Tract clicked
            st.session_state["selected_tract"] = str(point["location"]).split('.')[0].zfill(11)
            st.session_state["selected_anchor"] = None
        else: # Anchor clicked
            st.session_state["selected_anchor"] = point.get("customdata")
            st.session_state["selected_tract"] = None

with col_side:
    # --- MODE A: TRACT ANALYSIS ---
    if st.session_state["selected_tract"]:
        sid = st.session_state["selected_tract"]
        row = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        st.markdown(f"<h3 style='color:#00ff88;'>TRACT {sid}</h3>", unsafe_allow_html=True)
        # (Standard 8 metrics and nearby anchors code here...)
        
    # --- MODE B: ANCHOR CLUSTER ANALYSIS ---
    elif st.session_state["selected_anchor"]:
        target_name = st.session_state["selected_anchor"]
        anchor_row = anchor_df[anchor_df['name'] == target_name].iloc[0]
        st.markdown(f"<h3 style='color:#00ff88;'>ANCHOR: {target_name}</h3>", unsafe_allow_html=True)
        st.markdown(f"**TYPE:** {anchor_row.get('type', 'Institutional Asset').upper()}")
        
        st.divider()
        st.markdown("##### 🛰️ REGIONAL CLUSTER: 5 NEAREST ANCHORS")
        
        a_calc = anchor_df[anchor_df['name'] != target_name].copy()
        a_calc['dist'] = a_calc.apply(lambda x: calculate_distance(anchor_row['lat'], anchor_row['lon'], x['lat'], x['lon']), axis=1)
        
        for _, a in a_calc.sort_values('dist').head(5).iterrows():
            st.markdown(f"""
                <div class='anchor-card'>
                    <span style='color:#00ff88; font-weight:bold;'>{a['dist']:.1f} MI</span><br>
                    {a['name']}<br>
                    <small style='color:#94a3b8;'>{a.get('type', 'Asset').upper()}</small>
                </div>
            """, unsafe_allow_html=True)
            
    else:
        st.info("SELECT A TARGET TRACT OR ANCHOR ON THE MAP")