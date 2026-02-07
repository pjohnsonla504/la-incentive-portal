import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration (MUST be at the very top)
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")
curr_dir = os.path.dirname(os.path.abspath(__file__))

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

# --- AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    
    # We use a container to ensure the form is clearly rendered
    login_box = st.container(border=True)
    with login_box:
        u_in = st.text_input("Username").strip()
        p_in = st.text_input("Password", type="password").strip()
        
        if st.button("Access Portal"):
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = [c.strip() for c in db.columns]
                
                match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                
                if not match.empty:
                    st.session_state["authenticated"] = True
                    st.session_state["role"] = str(match.iloc[0]['Role'])
                    st.session_state["a_type"] = str(match.iloc[0]['Assigned_Type'])
                    st.session_state["a_val"] = str(match.iloc[0]['Assigned_Value'])
                    # FIX 1: Forced rerun ensures the script moves past the 'if not authenticated' block
                    st.rerun() 
                else:
                    st.error("Invalid Username or Password")
            except Exception as e:
                st.error(f"Authentication Error: {e}")
    
    # FIX 2: Explicit stop ensures NO code below this runs if user is not logged in
    st.stop() 

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    csv_path = os.path.join(curr_dir, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(curr_dir, "la_tracts_2024.json")

    # Load and clean GeoJSON
    with open(json_path) as f: 
        la_geojson = json.load(f)
    for feature in la_geojson['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_CLEAN'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Load and clean CSV
    df = pd.read_csv(csv_path)
    df.rename(columns={df.columns[1]: 'raw_geoid'}, inplace=True)
    df.columns = df.columns.str.strip().str.lower()
    df['geoid_clean'] = df['raw_geoid'].astype(str).apply(lambda x: "".join(re.findall(r'\d+', x))[-11:])
    
    # Broad Eligibility Mapping
    def get_status(row):
        # Checks Column Q (Insider) and Column P (ACS)
        insider = str(row.get('opportunity zones insiders eligibilty', '')).lower()
        acs = str(row.get('5-year acs eligiblity', '')).lower()
        try:
            pov = float(row.get('estimate!!percent below poverty level!!population for whom poverty status is determined', 0))
        except: pov = 0
        
        if any(x in ['yes', '1', 'true', 'eligible'] for x in [insider, acs]) or pov >= 20.0:
            return "Eligible"
        return "Ineligible"

    df['status'] = df.apply(get_status, axis=1)
    
    # Left Merge to GeoJSON to ensure all 620+ shapes are clickable
    all_map_ids = [f['properties']['GEOID_CLEAN'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_clean': all_map_ids})
    return pd.merge(map_df, df, on='geoid_clean', how='left').fillna({'status': 'Ineligible'}), la_geojson

# Load the data only AFTER authentication
master_df, la_geojson = load_data()

# --- MAIN DASHBOARD INTERFACE ---
st.title("📍 Louisiana OZ 2.0: Full Eligibility Map")

# FIX 3: Role-based filtering of the map view
m_df = master_df.copy()
if st.session_state.get("role", "").lower() != "admin":
    a_type = st.session_state.get("a_type", "").lower()
    a_val = st.session_state.get("a_val", "")
    if a_type in m_df.columns:
        m_df = m_df[m_df[a_type] == a_val]

# Layout Columns
col_map, col_details = st.columns([0.7, 0.3])

with col_map:
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid_clean", featureidkey="properties.GEOID_CLEAN",
        color="status",
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#D3D3D3"},
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6
    )
    fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0})
    
    map_selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_selection and "selection" in map_selection and map_selection["selection"]["points"]:
        st.session_state["selected_tract"] = map_selection["selection"]["points"][0]["location"]

with col_details:
    sid = st.session_state["selected_tract"]
    if sid:
        row = master_df[master_df['geoid_clean'] == sid].iloc[0]
        st.subheader(f"Tract {sid}")
        if row['status'] == "Eligible":
            st.success("✅ ELIGIBLE")
        else:
            st.warning("⚪ INELIGIBLE")
        st.write(f"**Parish:** {str(row.get('parish', 'N/A')).title()}")
    else:
        st.info("Click a tract on the map to view data.")