import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="OZ 2.0 Strategic Planner", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"GSheets Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# Haversine formula for distance calculation
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 # Miles
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.9

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Standardize GEOID
    geoid_header = "Geography11-digit FIPCode"
    df['GEOID_KEY'] = df[geoid_header].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    m_map = {
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "pop65": "Population 65 years and over",
        "home": "Median Home Value",
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)",
        "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)",
        "web": "Broadband Internet (%)",
        "dis": "Disability Population (%)"
    }

    # Load Boundaries & Extract Centers for distance math
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    
    centers = {}
    for feature in g['features']:
        gid = str(feature['properties'].get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feature['properties']['GEOID_MATCH'] = gid
        # Extract lat/lon from GeoJSON properties (INTPTLAT/INTPTLON are standard in TIGER files)
        try:
            centers[gid] = {
                "lat": float(feature['properties'].get('INTPTLAT', 0)),
                "lon": float(feature['properties'].get('INTPTLON', 0))
            }
        except: pass

    # Load Anchors
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    return df, g, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION (Omitted for brevity) ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Access")
    # ... (Login Logic)
    st.stop()

# --- 4. DATA PROCESSING ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

elig_col = "5-year ACS Eligiblity"
u_df['map_status'] = np.where(
    u_df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 
    "Eligible", "Ineligible"
)

# Tracker
try:
    current_sheet = conn.read(worksheet="Sheet1", ttl=0)
    user_count = len(current_sheet[current_sheet['User'] == st.session_state["username"]])
except: user_count = 0; current_sheet = pd.DataFrame()

# --- 5. INTERFACE ---
st.title(f"📍 OZ 2.0 Strategic Planner: {st.session_state['a_val']}")
st.divider()

col_map, col_data = st.columns([0.6, 0.4])

with col_map:
    
    fig = px.choropleth_mapbox(
        u_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="map_status", 
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "rgba(0,0,0,0)"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 30.8, "lon": -91.5},
        opacity=0.7, hover_data=["GEOID_KEY", "Parish"]
    )
    fig.update_traces(marker_line_width=1.5, marker_line_color="dimgrey")

    if not anchor_df.empty:
        fig.add_scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=10, color='black', symbol='diamond'),
            text=anchor_df['name'], name='Anchors'
        )

    fig.update_layout(height=800, margin={"r":0,"t":0,"l":0,"b":0})
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if selected and selected.get("selection") and selected["selection"].get("points"):
        st.session_state["selected_tract"] = str(selected["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_data:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.subheader(f"Tract: {sid}")
        
        # --- Metrics ---
        st.markdown("##### 📊 Demographics")
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Population", row.get(M_MAP["pop"]))
            st.metric("Pop. 65+", row.get(M_MAP["pop65"]))
            st.metric("Poverty %", row.get(M_MAP["poverty"]))
        with m2:
            st.metric("Med. Income", row.get(M_MAP["income"]))
            st.metric("Med. Home", row.get(M_MAP["home"]))
            st.metric("Broadband %", row.get(M_MAP["web"]))

        # --- ⚓ ANCHOR CALCULATION (USING GEOJSON CENTERS) ---
        st.divider()
        st.markdown("##### ⚓ 5 Nearest Anchor Assets")
        
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            # Create a copy to avoid settings warnings
            local_anchors = anchor_df.copy()
            local_anchors['dist'] = local_anchors.apply(
                lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1
            )
            nearest = local_anchors.sort_values('dist').head(5)
            
            # Display as Metric Cards or Table
            for _, a in nearest.iterrows():
                col_a, col_b = st.columns([0.7, 0.3])
                col_a.markdown(f"**{a['name']}** \n*{a['type']}*")
                col_b.metric("Dist", f"{a['dist']:.1f}mi")
        else:
            st.warning("Coordinates not found in GeoJSON properties for this tract.")

        # --- Submission ---
        st.divider()
        st.markdown("##### ✍️ Submission")
        note = st.text_area("Justification")
        if st.button("Submit Recommendation", type="primary"):
            # (Submission logic)
            st.success("Tract Recorded")
    else:
        st.info("Click a highlighted tract on the map.")