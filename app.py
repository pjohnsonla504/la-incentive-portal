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

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.9

# --- 2. DATA LOADING & FUZZY HEADER MATCHING ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip() # Clean invisible spaces
    
    # DYNAMIC GEOID FINDER: Look for specific string, then fuzzy, then fallback to Column 1 (B)
    geoid_target = "Geography11-digit FIPCode"
    if geoid_target in df.columns:
        geoid_col = geoid_target
    else:
        # Fuzzy match for 'FIP' or 'digit' in headers
        fuzzy_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
        geoid_col = fuzzy_match[0] if fuzzy_match else df.columns[1]
    
    df['GEOID_KEY'] = df[geoid_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Demographic Mapping
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

    # Boundaries & Centroids from GeoJSON
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    
    centers = {}
    for feature in g['features']:
        gid = str(feature['properties'].get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feature['properties']['GEOID_MATCH'] = gid
        # Most TIGER GeoJSONs use INTPTLAT/INTPTLON
        try:
            centers[gid] = {
                "lat": float(feature['properties'].get('INTPTLAT', 0)),
                "lon": float(feature['properties'].get('INTPTLON', 0))
            }
        except: pass

    # Anchors
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    return df, g, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Access")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login"):
            u, p = st.text_input("User").strip(), st.text_input("Pass", type="password").strip()
            if st.form_submit_button("Login"):
                user_db = conn.read(worksheet="Users", ttl=0)
                user_db.columns = user_db.columns.str.strip()
                match = user_db[(user_db['Username'].astype(str) == u) & (user_db['Password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True, "username": u, 
                        "role": str(match.iloc[0]['Role']), 
                        "a_type": str(match.iloc[0]['Assigned_Type']), 
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# --- 4. REGIONAL FILTERING ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

elig_col = "5-year ACS Eligiblity"
u_df['map_status'] = np.where(
    u_df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 
    "Eligible", "Ineligible"
)

# --- 5. INTERFACE ---
st.title(f"📍 OZ 2.0 Strategic Planner: {st.session_state['a_val']}")
st.divider()

col_map, col_data = st.columns([0.6, 0.4])

with col_map:
    # Map Visualization
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
        raw_sel = str(selected["selection"]["points"][0].get("location")).split('.')[0].zfill(11)
        st.session_state["selected_tract"] = raw_sel

with col_data:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.subheader(f"Tract Profile: {sid}")
        
        # Demographics
        st.markdown("##### 📊 Census Data")
        m1, m2 = st.columns(2)
        with m1:
            st.metric("Total Population", row.get(M_MAP["pop"], "N/A"))
            st.metric("Poverty %", row.get(M_MAP["poverty"], "N/A"))
            st.metric("Unemployment", row.get(M_MAP["unemp"], "N/A"))
        with m2:
            st.metric("Med. Family Income", row.get(M_MAP["income"], "N/A"))
            st.metric("Pop. 65+", row.get(M_MAP["pop65"], "N/A"))
            st.metric("Broadband %", row.get(M_MAP["web"], "N/A"))

        # Nearest Anchors
        st.divider()
        st.markdown("##### ⚓ Nearest Anchor Assets")
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            local_anchors = anchor_df.copy()
            local_anchors['dist'] = local_anchors.apply(
                lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1
            )
            nearest = local_anchors.sort_values('dist').head(5)
            for _, a in nearest.iterrows():
                st.write(f"**{a['name']}** ({a.get('type', 'Anchor')}) — `{a['dist']:.1f} miles`")
        else:
            st.caption("Coordinate data for this tract is missing in GeoJSON.")

        # Submission
        st.divider()
        st.markdown("##### ✍️ Submission")
        note = st.text_area("Justification")
        if st.button("Submit Recommendation", type="primary"):
            st.success("Tract Recorded")
    else:
        st.info("Click a Green tract on the map to see details.")