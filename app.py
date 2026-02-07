import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. LAPTOP OPTIMIZED CONFIG ---
st.set_page_config(page_title="OZ 2.0 Planner", layout="wide")

st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 0rem;}
    [data-testid="stMetricValue"] {font-size: 1.4rem !important;}
    .stMetric {background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e1e4e8;}
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"GSheets Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# Robust Distance Logic
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 # Miles
        p1, p2 = np.radians(float(lat1)), np.radians(float(lat2))
        dp, dl = np.radians(float(lat2)-float(lat1)), np.radians(float(lon2)-float(lon1))
        a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.0

# Safe Number Formatting (Fixes ValueError)
def safe_num(val, is_money=False):
    try:
        if pd.isna(val) or str(val).strip().lower() in ['n/a', 'nan', '']: return "N/A"
        n = float(str(val).replace('$', '').replace(',', '').replace('%', '').strip())
        return f"${n:,.0f}" if is_money else f"{n:,.0f}"
    except: return str(val)

# --- 2. DATA LOADING & CENTROID FALLBACK ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Locate GEOID column
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    with open("tl_2025_22_tract.json") as f: 
        gj = json.load(f)
    
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        
        # Fallback: If properties lack lat/lon, calculate from the shape coordinates
        lat = p.get('INTPTLAT') or p.get('LATITUDE')
        lon = p.get('INTPTLON') or p.get('LONGITUDE')
        
        if not lat and feat['geometry']['type'] in ['Polygon', 'MultiPolygon']:
            pts = []
            coords = feat['geometry']['coordinates']
            if feat['geometry']['type'] == 'Polygon': pts = coords[0]
            else: 
                for poly in coords: pts.extend(poly[0])
            lon = np.mean([pt[0] for pt in pts])
            lat = np.mean([pt[1] for pt in pts])
        
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}

    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    m_map = {
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "web": "Broadband Internet (%)"
    }
    return df, gj, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    # ... Login Form logic ...
    st.stop()

# --- 4. DASHBOARD INTERFACE ---
st.subheader(f"📍 OZ 2.0 Planner: {st.session_state['a_val']}")

col_map, col_side = st.columns([0.6, 0.4])

with col_map:
    # Optimized map height for laptop screens
    fig = px.choropleth_mapbox(
        master_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="5-year ACS Eligiblity", 
        color_discrete_map={"Eligible": "#28a745", "Yes": "#28a745", "Ineligible": "rgba(0,0,0,0)"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 30.8, "lon": -91.5},
        opacity=0.6
    )
    if not anchor_df.empty:
        fig.add_scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=7, color='black', symbol='diamond'), text=anchor_df['name']
        )
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False)
    
    select_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if select_data and select_data.get("selection") and select_data["selection"].get("points"):
        st.session_state["selected_tract"] = str(select_data["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_side:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"#### Tract {sid} Summary")
        
        # 2x2 Metric Grid (Laptop Friendly)
        m1, m2 = st.columns(2)
        m1.metric("Family Income", safe_num(row.get(M_MAP["income"]), True))
        m2.metric("Poverty Rate", f"{safe_num(row.get(M_MAP['poverty']))}%")
        
        m3, m4 = st.columns(2)
        m3.metric("Total Population", safe_num(row.get(M_MAP["pop"])))
        m4.metric("Broadband %", f"{safe_num(row.get(M_MAP['web']))}%")

        st.markdown("---")
        st.markdown("##### ⚓ Nearest Anchor Assets")
        
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            # Anchors distance using 'lat' and 'lon' column headers
            anchors = anchor_df.copy()
            anchors['dist'] = anchors.apply(lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1)
            nearest = anchors.sort_values('dist').head(5)
            
            for _, a in nearest.iterrows():
                st.write(f"**{a['dist']:.1f} mi** — {a['name']} <small>({a['type']})</small>", unsafe_allow_html=True)
        else:
            st.info("Select a tract to calculate proximity to anchors.")

        st.markdown("---")
        note = st.text_area("Investment Justification", height=80)
        if st.button("Submit Recommendation", type="primary", use_container_width=True):
            st.success("Tract Nomination Saved")
    else:
        st.info("👆 Click a green census tract on the map to begin analysis.")