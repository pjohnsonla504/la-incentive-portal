import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="OZ 2.0 Planner", layout="wide")

# CSS to optimize laptop viewing (metrics & map scaling)
st.markdown("""
    <style>
    .block-container {padding-top: 1.5rem; padding-bottom: 0rem;}
    [data-testid="stMetricValue"] {font-size: 1.3rem !important;}
    .stMetric {background-color: #f8f9fa; padding: 10px; border-radius: 8px;}
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
        phi1, phi2 = np.radians(float(lat1)), np.radians(float(lat2))
        dphi, dlambda = np.radians(float(lat2)-float(lat1)), np.radians(float(lon2)-float(lon1))
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.9

# Helper to safely format currency/numbers from mixed data
def safe_format(val, is_currency=False):
    try:
        if pd.isna(val) or val == "N/A": return "N/A"
        # Strip any existing currency symbols or commas
        clean_val = float(str(val).replace('$', '').replace(',', '').strip())
        if is_currency:
            return f"${clean_val:,.0f}"
        return f"{clean_val:,.0f}"
    except:
        return str(val)

# --- 2. DATA LOADING & ROBUST COORDINATE EXTRACTION ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    fuzzy_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    geoid_col = fuzzy_match[0] if fuzzy_match else df.columns[1]
    df['GEOID_KEY'] = df[geoid_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    
    centers = {}
    for feature in g['features']:
        p = feature['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feature['properties']['GEOID_MATCH'] = gid
        
        # Robust check for any lat/lon naming convention
        lat_keys = ['INTPTLAT', 'LATITUDE', 'LAT', 'CenLat', 'CENTROID_Y']
        lon_keys = ['INTPTLON', 'LONGITUDE', 'LON', 'CenLon', 'CENTROID_X']
        
        lat = next((p.get(k) for k in lat_keys if p.get(k)), None)
        lon = next((p.get(k) for k in lon_keys if p.get(k)), None)
        
        if lat and lon:
            try:
                # Remove '+' signs often found in Census strings
                centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}
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

# --- 3. AUTHENTICATION (Logic remains same) ---
if not st.session_state["authenticated"]:
    # ... Login Form ...
    st.stop()

# --- 4. MAP & INTERFACE ---
st.subheader(f"📍 Strategic Planner: {st.session_state['a_val']}")

col_map, col_data = st.columns([0.55, 0.45])

with col_map:
    fig = px.choropleth_mapbox(
        master_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="5-year ACS Eligiblity", 
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "rgba(0,0,0,0)", "Yes": "#28a745"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 31.0, "lon": -91.8}
    )
    if not anchor_df.empty:
        fig.add_scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=8, color='black', symbol='diamond'), text=anchor_df['name']
        )
    fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False)
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if selected and selected.get("selection") and selected["selection"].get("points"):
        st.session_state["selected_tract"] = str(selected["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_data:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"### Tract {sid}")
        
        # FIXED METRIC CARDS: Laptop-sized & Error-proof
        m1, m2 = st.columns(2)
        m1.metric("Med. Family Income", safe_format(row.get(M_MAP["income"]), True))
        m2.metric("Poverty Rate", f"{safe_format(row.get(M_MAP['poverty']))}%")
        
        m3, m4 = st.columns(2)
        m3.metric("Population", safe_format(row.get(M_MAP["pop"])))
        m4.metric("Broadband %", f"{safe_format(row.get(M_MAP['web']))}%")

        # ANCHOR SECTION
        st.divider()
        st.markdown("##### ⚓ 5 Nearest Anchors")
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            local_anchors = anchor_df.copy()
            local_anchors['dist'] = local_anchors.apply(
                lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1
            )
            nearest = local_anchors.sort_values('dist').head(5)
            for _, a in nearest.iterrows():
                st.write(f"**{a['dist']:.1f} mi** — {a['name']} <small>({a['type']})</small>", unsafe_allow_html=True)
        else:
            st.warning("Coordinate keys not found in GeoJSON. Checking: INTPTLAT, LATITUDE, CenLat...")

        # SUBMISSION
        st.divider()
        note = st.text_area("Justification", height=100)
        if st.button("Submit Recommendation", type="primary", use_container_width=True):
            st.success("Submitted!")
    else:
        st.info("Click a tract on the map to begin.")