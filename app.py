import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="OZ 2.0 Strategic Planner", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# Haversine Distance for Anchor Assets
def get_distance(lat1, lon1, lat2, lon2):
    r = 3958.8 
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- 2. DATA LOADING & DUAL-FILE JOIN ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master File (Eligibility & Assignments)
    master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    master.columns = master.columns.str.strip()
    # GEOID is usually Column B (Index 1)
    master['GEOID_KEY'] = master[master.columns[1]].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Load Demographics File (Metric Cards)
    demo = pd.read_csv("Louisiana_All_Tracts_Demographics.csv")
    demo.columns = demo.columns.str.strip()
    # GEOID is usually Column A (Index 0)
    demo['GEOID_KEY'] = demo[demo.columns[0]].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Merge Files
    m = pd.merge(master, demo, on='GEOID_KEY', how='left', suffixes=('', '_demo'))
    
    # Fuzzy Matcher for Demographic Columns
    def get_col(df, keys):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keys): return col
        return None

    metrics_map = {
        "pop": get_col(m, ["Total", "Population"]),
        "home": get_col(m, ["Median", "Home", "Value"]),
        "medicaid": get_col(m, ["Medicaid", "Public"]),
        "income": get_col(m, ["Median", "Family", "Income"]),
        "poverty": get_col(m, ["Poverty", "Rate"]),
        "labor": get_col(m, ["Labor", "Force", "Participation"]),
        "unemp": get_col(m, ["Unemployment", "Rate"]),
        "hs": get_col(m, ["HS", "Degree"]),
        "bach": get_col(m, ["Bachelor"]),
        "web": get_col(m, ["Broadband"]),
        "dis": get_col(m, ["Disability"])
    }

    elig_col = get_col(m, ["5-Year", "ACS", "Eligiblity"])

    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        # Force strict 11-digit matching for GeoJSON properties
        feature['properties']['GEOID_MATCH'] = str(feature['properties'].get('GEOID', ''))[-11:]

    # Load Anchor Assets
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip().str.lower()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
        
    return m, g, a, elig_col, metrics_map

master_df, la_geojson, anchor_df, ELIG_COL, M_MAP = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Recommendation Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in, p_in = st.text_input("Username").strip(), st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = db.columns.str.strip()
                match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True, "username": u_in, 
                        "role": str(match.iloc[0]['Role']), 
                        "a_type": str(match.iloc[0]['Assigned_Type']), 
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# --- 4. REGIONAL FILTERING & TRACKING ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Eligibility Status for Map (Eligible vs Ineligible)
if ELIG_COL:
    u_df['map_status'] = np.where(u_df[ELIG_COL].astype(str).str.lower().str.contains('yes|eligible', na=False), "Eligible", "Ineligible")
else:
    u_df['map_status'] = "Ineligible"

# Budget Counter (25% of eligible region)
total_eligible = len(u_df[u_df['map_status'] == "Eligible"])
q_limit = max(1, int(total_eligible * 0.25))

# Tracker: Read current nominations from Sheet1
try:
    recs_sheet = conn.read(worksheet="Sheet1", ttl=0)
    current_recs = len(recs_sheet[recs_sheet['User'] == st.session_state["username"]])
except:
    current_recs = 0
    recs_sheet = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification"])

# --- 5. TOP PANEL: PROGRESS ---
st.title(f"📍 OZ 2.0 Strategic Planner: {st.session_state['a_val']}")
c_prog, c_stat = st.columns([0.7, 0.3])
with c_prog:
    st.progress(min(1.0, current_recs / q_limit), text=f"Budget Used: {current_recs} of {q_limit} (25% Threshold)")
with c_stat:
    st.metric("Tracts Recommended", f"{current_recs}")

st.divider()

# --- 6. MAIN INTERFACE (2/3 MAP | 1/3 PROFILE) ---
col_map, col_profile = st.columns([0.66, 0.33])

with col_map:
    
    fig = px.choropleth_mapbox(
        u_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="map_status", 
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#737373"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 30.8, "lon": -91.5},
        opacity=0.7, hover_data=["GEOID_KEY", "Parish", "Region"]
    )
    fig.update_layout(height=850, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", y=1.02))
    
    sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if sel and sel.get("selection") and sel["selection"].get("points"):
        st.session_state["selected_tract"] = sel["selection"]["points"][0].get("location")

with col_profile:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    
    if sid:
        # Get data for the selected tract from the merged dataframe
        res = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        
        # Identity
        st.markdown(f"#### Tract ID: `{sid}`")
        st.write(f"**Parish:** {res.get('Parish', 'N/A')}")
        st.write(f"**Region:** {res.get('Region', 'N/A')}")
        
        st.divider()
        
        # 11 Demographic Metrics
        st.markdown("##### 📊 Demographic Snapshot")
        def disp_metric(label, key):
            col_name = M_MAP.get(key)
            val = res.get(col_name, "N/A") if col_name else "N/A"
            st.metric(label, val)

        m1, m2 = st.columns(2)
        with m1:
            disp_metric("Total Population", "pop")
            disp_metric("% Medicaid/Public", "medicaid")
            disp_metric("Poverty Rate (%)", "poverty")
            disp_metric("Unemployment (%)", "unemp")
            disp_metric("Bachelor's+", "bach")
            disp_metric("Disability %", "dis")
        with m2:
            disp_metric("Median Home Val", "home")
            disp_metric("Median Income", "income")
            disp_metric("Labor Force %", "labor")
            disp_metric("HS Degree+", "hs")
            disp_metric("Broadband %", "web")

        # Justification Area
        st.divider()
        st.markdown("##### ✍️ Recommendation Justification")
        j_cat = st.selectbox("Justification Category", ["Economic Growth", "Infrastructure", "Housing", "Workforce Development", "Other"])
        j_text = st.text_area("Written Justification", placeholder="Describe the strategic potential...")
        
        if st.button("Submit Recommendation", type="primary"):
            if current_recs >= q_limit:
                st.warning("You have reached your 25% recommendation limit for this region.")
            else:
                new_entry = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                    "User": st.session_state["username"],
                    "GEOID": sid,
                    "Category": j_cat,
                    "Justification": j_text
                }])
                try:
                    updated_sheet = pd.concat([recs_sheet, new_entry], ignore_index=True)
                    conn.update(worksheet="Sheet1", data=updated_sheet)
                    st.success(f"Tract {sid} nominated!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Submission Error: {e}")

        # Nearest Anchors
        st.divider()
        st.markdown("##### ⚓ 5 Nearest Anchor Assets")
        if not anchor_df.empty:
            # Lat/Lon are pulled from the master file or demographics file
            # If not present, this section is skipped
            try:
                anchor_df['dist'] = anchor_