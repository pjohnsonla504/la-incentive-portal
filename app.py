import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION (Optimized for Laptop) ---
st.set_page_config(page_title="OZ 2.0 Planner", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS to tighten the UI for smaller screens
st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 0rem;}
    .stMetric {padding: 5px; border: 1px solid #f0f2f6; border-radius: 5px;}
    [data-testid="stMetricValue"] {font-size: 1.5rem !important;}
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"GSheets Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.9

# --- 2. DATA LOADING & ROBUST COORDINATE EXTRACTION ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Fuzzy GEOID Match
    fuzzy_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    geoid_col = fuzzy_match[0] if fuzzy_match else df.columns[1]
    df['GEOID_KEY'] = df[geoid_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    
    centers = {}
    for feature in g['features']:
        props = feature['properties']
        gid = str(props.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feature['properties']['GEOID_MATCH'] = gid
        
        # Check multiple possible lat/lon keys found in various GeoJSON formats
        lat = props.get('INTPTLAT') or props.get('LATITUDE') or props.get('CenLat') or props.get('lat')
        lon = props.get('INTPTLON') or props.get('LONGITUDE') or props.get('CenLon') or props.get('lon')
        
        if lat and lon:
            try: centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}
            except: pass

    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    m_map = {
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "pop65": "Population 65 years and over",
        "home": "Median Home Value",
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "web": "Broadband Internet (%)",
        "unemp": "Unemployment Rate (%)"
    }

    return df, g, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 OZ 2.0 Planner")
    with st.form("login"):
        u, p = st.text_input("User").strip(), st.text_input("Pass", type="password").strip()
        if st.form_submit_button("Login"):
            user_db = conn.read(worksheet="Users", ttl=0)
            match = user_db[(user_db['Username'].astype(str) == u) & (user_db['Password'].astype(str) == p)]
            if not match.empty:
                st.session_state.update({"authenticated": True, "username": u, "role": str(match.iloc[0]['Role']), "a_type": str(match.iloc[0]['Assigned_Type']), "a_val": str(match.iloc[0]['Assigned_Value'])})
                st.rerun()
    st.stop()

# --- 4. DATA PROCESSING ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

elig_col = "5-year ACS Eligiblity"
u_df['map_status'] = np.where(u_df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), "Eligible", "Ineligible")

# --- 5. INTERFACE (Laptop Optimized) ---
st.subheader(f"📍 {st.session_state['a_val']} Region")

col_map, col_data = st.columns([0.55, 0.45])

with col_map:
    
    fig = px.choropleth_mapbox(
        u_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="map_status", color_discrete_map={"Eligible": "#28a745", "Ineligible": "rgba(0,0,0,0)"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 30.8, "lon": -91.5},
        opacity=0.7
    )
    fig.update_traces(marker_line_width=1.2, marker_line_color="dimgrey")

    if not anchor_df.empty:
        fig.add_scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=8, color='black', symbol='diamond'), text=anchor_df['name'], name='Anchors'
        )

    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False)
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if selected and selected.get("selection") and selected["selection"].get("points"):
        st.session_state["selected_tract"] = str(selected["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_data:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.caption(f"SELECTED TRACT: **{sid}** | {row.get('Parish')}")
        
        # 4-Column Compact Metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Pop", row.get(M_MAP["pop"], "N/A"))
        m2.metric("Poverty", f"{row.get(M_MAP['poverty'], 'N/A')}%")
        m3.metric("Income", f"${row.get(M_MAP['income'], '0'):,.00}")
        m4.metric("Age 65+", row.get(M_MAP["pop65"], "N/A"))

        # Compact Anchor List
        st.markdown("---")
        st.markdown("<h6 style='margin-bottom:0px;'>⚓ 5 Nearest Anchors</h6>", unsafe_allow_html=True)
        t_coord = tract_centers.get(sid)
        if t_coord:
            local_anchors = anchor_df.copy()
            local_anchors['dist'] = local_anchors.apply(lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1)
            nearest = local_anchors.sort_values('dist').head(5)
            for _, a in nearest.iterrows():
                st.write(f"**{a['dist']:.1f}mi** — {a['name']} <small>({a['type']})</small>", unsafe_allow_html=True)
        else:
            st.warning("⚠️ GeoJSON missing INTPTLAT/LATITUDE properties.")

        # Compact Submission
        st.markdown("---")
        note = st.text_area("Justification", height=80, placeholder="Explain selection...")
        if st.button("Submit Recommendation", type="primary", use_container_width=True):
            st.success("Tract Nominated")
    else:
        st.info("Click a Green tract to view demographics.")