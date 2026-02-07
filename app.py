# --- 1. IMPORTS (MUST BE FIRST) ---
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from streamlit_gsheets import GSheetsConnection

# --- 2. PAGE CONFIG (MUST BE SECOND) ---
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")

# --- 3. SESSION STATE INITIALIZATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

# Base directory for cloud path handling
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 4. AUTHENTICATION BLOCK ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.container(border=True):
        u_in = st.text_input("Username").strip()
        p_in = st.text_input("Password", type="password").strip()
        
        if st.button("Access Portal"):
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = [c.strip() for c in db.columns]
                match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True,
                        "role": str(match.iloc[0]['Role']),
                        "a_type": str(match.iloc[0]['Assigned_Type']),
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else:
                    st.error("Invalid credentials")
            except Exception as e:
                st.error(f"Login Error: {e}")
    st.stop()

# --- 5. DATA LOADING (STRICT PATHS & 620-TRACT LOGIC) ---
@st.cache_data(ttl=60)
def load_data():
    csv_path = os.path.join(BASE_DIR, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(BASE_DIR, "la_tracts_2024.json")

    # Load GeoJSON
    with open(json_path) as f: 
        la_geojson = json.load(f)
    for feature in la_geojson['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_CLEAN'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Load CSV
    df = pd.read_csv(csv_path)
    df.rename(columns={df.columns[1]: 'raw_geoid'}, inplace=True)
    df.columns = df.columns.str.strip().str.lower()
    df['geoid_clean'] = df['raw_geoid'].astype(str).apply(lambda x: "".join(re.findall(r'\d+', x))[-11:])
    
    # Header Mapping for Eligibility
    # Column Q: opportunity zones insiders eligibilty
    # Column P: 5-year acs eligiblity
    def get_status(row):
        insider = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip()
        acs = str(row.get('5-year acs eligiblity', '')).lower().strip()
        try:
            pov = float(row.get('estimate!!percent below poverty level!!population for whom poverty status is determined', 0))
        except: pov = 0
        
        # Highlight green if designated in Q, P, OR if poverty math hits the 20% threshold
        if any(x in ['yes', '1', 'true', 'eligible'] for x in [insider, acs]) or pov >= 20.0:
            return "Eligible"
        return "Ineligible"

    df['status'] = df.apply(get_status, axis=1)
    
    # Ensure map shapes and CSV data match perfectly
    all_map_ids = [f['properties']['GEOID_CLEAN'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_clean': all_map_ids})
    return pd.merge(map_df, df, on='geoid_clean', how='left').fillna({'status': 'Ineligible'}), la_geojson

master_df, la_geojson = load_data()

# --- 6. DASHBOARD INTERFACE ---
st.title("📍 Louisiana OZ 2.0: Full Eligibility Map")
eligible_count = len(master_df[master_df['status'] == "Eligible"])
st.sidebar.metric("Total Eligible Tracts", eligible_count)

# Admin/User Filtering
m_df = master_df.copy()
if st.session_state["role"].lower() != "admin":
    a_type = st.session_state["a_type"].lower()
    if a_type in m_df.columns:
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

# Layout
col_map, col_info = st.columns([0.65, 0.35])

with col_map:
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid_clean", featureidkey="properties.GEOID_CLEAN",
        color="status",
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#D3D3D3"},
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["geoid_clean", "parish"]
    )
    fig.update_layout(height=750, margin={"r":0,"t":0,"l":0,"b":0})
    
    map_sub = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_sub and "selection" in map_sub and map_sub["selection"]["points"]:
        st.session_state["selected_tract"] = map_sub["selection"]["points"][0]["location"]

with col_info:
    sid = st.session_state["selected_tract"]
    if sid:
        res = master_df[master_df['geoid_clean'] == sid].iloc[0]
        st.header(f"Tract {sid}")
        if res['status'] == "Eligible":
            st.success("✅ FULLY ELIGIBLE (OZ 2.0)")
        else:
            st.warning("⚪ INELIGIBLE")
        
        st.write(f"**Parish:** {str(res.get('parish', 'N/A')).title()}")
        st.metric("Poverty Rate", f"{res.get('poverty_rate', 0)}%")
    else:
        st.info("Select a tract to view eligibility data.")