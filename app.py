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

def get_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        phi1, phi2 = np.radians(lat1), np.radians(lat2)
        dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
        a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return None

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Standardize GEOID
    geoid_header = "Geography11-digit FIPCode"
    if geoid_header not in df.columns:
        geoid_header = df.columns[1]
    df['GEOID_KEY'] = df[geoid_header].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Exact Header Mapping
    m_map = {
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "home": "Median Home Value",
        "medicaid": "% Medicaid/Public Insurance",
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)",
        "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)",
        "web": "Broadband Internet (%)",
        "dis": "Disability Population (%)"
    }

    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = raw_id.split('.')[0][-11:].zfill(11)

    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip().str.lower()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
        
    return df, g, a, m_map

master_df, la_geojson, anchor_df, M_MAP = load_data()

# --- 3. AUTHENTICATION (Omitted for brevity - logic remains same as v14) ---
if not st.session_state["authenticated"]:
    # ... (Login form logic)
    st.stop()

# --- 4. REGIONAL FILTERING & COLOR SCHEME LOGIC ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# FIXED COLOR LOGIC: Green for Eligible, Grey for Ineligible
elig_col = "5-year ACS Eligiblity"
u_df['map_status'] = np.where(
    u_df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 
    "Eligible", 
    "Ineligible"
)

# Budgeting
regional_eligible = len(u_df[u_df['map_status'] == "Eligible"])
quota = max(1, int(regional_eligible * 0.25))

try:
    current_sheet = conn.read(worksheet="Sheet1", ttl=0)
    user_recs = current_sheet[current_sheet['User'] == st.session_state["username"]]
    user_count = len(user_recs)
except:
    user_count = 0
    current_sheet = pd.DataFrame()

# --- 5. INTERFACE ---
st.title(f"📍 OZ 2.0 Strategic Planner: {st.session_state['a_val']}")
c_bar, c_num = st.columns([0.7, 0.3])
c_bar.progress(min(1.0, user_count/quota), text=f"Tracts Recommended: {user_count} / {quota}")
c_num.metric("My Total Nominations", user_count)

st.divider()

col_map, col_data = st.columns([0.66, 0.33])

with col_map:
    # Explicitly mapping colors to categorical values
    fig = px.choropleth_mapbox(
        u_df, 
        geojson=la_geojson, 
        locations="GEOID_KEY", 
        featureidkey="properties.GEOID_MATCH",
        color="map_status", 
        color_discrete_map={
            "Eligible": "#28a745",    # True Green
            "Ineligible": "#6c757d"   # Bootstrap Grey
        },
        category_orders={"map_status": ["Eligible", "Ineligible"]},
        mapbox_style="carto-positron", 
        zoom=7, 
        center={"lat": 30.8, "lon": -91.5},
        opacity=0.7, 
        hover_data=["GEOID_KEY", "Parish"]
    )
    fig.update_layout(
        height=800, 
        margin={"r":0,"t":0,"l":0,"b":0},
        legend=dict(title="Status", orientation="h", y=1.02, x=0)
    )
    
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected and selected.get("selection") and selected["selection"].get("points"):
        raw_sel = str(selected["selection"]["points"][0].get("location"))
        st.session_state["selected_tract"] = raw_sel.split('.')[0].zfill(11)

with col_data:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    matching_rows = master_df[master_df['GEOID_KEY'] == sid]
    
    if sid and not matching_rows.empty:
        row = matching_rows.iloc[0]
        st.write(f"**ID:** `{sid}` | **Parish:** {row.get('Parish')} | **Region:** {row.get('Region')}")
        
        # Determine status for profile display
        is_elig = row[elig_col].lower().strip() in ['yes', 'eligible', 'y']
        status_color = "green" if is_elig else "grey"
        st.markdown(f"**Status:** :{status_color}[{'Eligible for OZ 2.0' if is_elig else 'Ineligible'}]")
        
        st.divider()
        st.markdown("##### 📊 Demographics")
        def show(lbl, k):
            h = M_MAP.get(k)
            val = row.get(h, "N/A")
            st.metric(lbl, val)

        m1, m2 = st.columns(2)
        with m1:
            show("Population", "pop")
            show("Poverty %", "poverty")
            show("Unemployment", "unemp")
            show("Bachelor's+", "bach")
            show("Disability %", "dis")
        with m2:
            show("Median Home", "home")
            show("Median Income", "income")
            show("Labor Part. %", "labor")
            show("HS Degree+", "hs")
            show("Broadband %", "web")

        st.divider()
        st.markdown("##### ✍️ Submission")
        # ... (Submission form logic)
    else:
        st.info("Select a tract on the map to view data.")