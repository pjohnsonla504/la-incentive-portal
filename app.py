# --- 1. IMPORTS ---
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from streamlit_gsheets import GSheetsConnection

# --- 2. PAGE CONFIG ---
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")

# Get the absolute path to the directory this script is in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 3. SESSION STATE ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

# --- 4. AUTHENTICATION ---
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

# --- 5. DATA LOADING (FIXED PATHS) ---
@st.cache_data(ttl=60)
def load_data():
    # Constructing paths that work on Streamlit Cloud
    csv_path = os.path.join(BASE_DIR, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(BASE_DIR, "la_tracts_2024.json")

    # Load GeoJSON
    try:
        with open(json_path) as f: 
            la_geojson = json.load(f)
    except FileNotFoundError:
        st.error(f"Missing File: la_tracts_2024.json not found at {json_path}")
        st.stop()

    for feature in la_geojson['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        # Normalize to 11 digits
        feature['properties']['GEOID_CLEAN'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Load CSV
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        st.error(f"Missing File: CSV not found at {csv_path}")
        st.stop()

    df.rename(columns={df.columns[1]: 'raw_geoid'}, inplace=True)
    df.columns = df.columns.str.strip().str.lower()
    df['geoid_clean'] = df['raw_geoid'].astype(str).apply(lambda x: "".join(re.findall(r'\d+', x))[-11:])
    
    # 620-Tract Eligibility Logic (Column Q and P + Math)
    def get_status(row):
        # Column Q: opportunity zones insiders eligibilty
        # Column P: 5-year acs eligiblity
        insider = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip()
        acs = str(row.get('5-year acs eligiblity', '')).lower().strip()
        try:
            pov_val = str(row.get('estimate!!percent below poverty level!!population for whom poverty status is determined', '0')).replace('%','')
            pov = float(pov_val)
        except: pov = 0
        
        # Binary check for "Green" status
        if any(x in ['yes', '1', 'true', 'eligible'] for x in [insider, acs]) or pov >= 20.0:
            return "Eligible"
        return "Ineligible"

    df['status'] = df.apply(get_status, axis=1)
    
    # Merge with map to ensure all tracts exist in the dataframe
    all_map_ids = [f['properties']['GEOID_CLEAN'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_clean': all_map_ids})
    merged = pd.merge(map_df, df, on='geoid_clean', how='left').fillna({'status': 'Ineligible', 'parish': 'N/A'})
    return merged, la_geojson

master_df, la_geojson = load_data()

# --- 6. INTERFACE ---
st.title("📍 Louisiana OZ 2.0 Master Data File")
st.sidebar.metric("Eligible Tracts (Green)", len(master_df[master_df['status'] == "Eligible"]))

m_df = master_df.copy()
if st.session_state["role"].lower() != "admin":
    a_type = st.session_state["a_type"].lower()
    if a_type in m_df.columns:
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

col_map, col_profile = st.columns([0.6, 0.4])

with col_map:
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid_clean", featureidkey="properties.GEOID_CLEAN",
        color="status",
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#D3D3D3"},
        mapbox_style="carto-positron", zoom=5.8, center={"lat": 30.9, "lon": -91.9},
        opacity=0.6, hover_data=["geoid_clean", "parish"]
    )
    fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0})
    
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if selected and "selection" in selected and selected["selection"]["points"]:
        st.session_state["selected_tract"] = selected["selection"]["points"][0]["location"]

with col_profile:
    sid = st.session_state["selected_tract"]
    if sid:
        res = master_df[master_df['geoid_clean'] == sid].iloc[0]
        st.subheader(f"Tract {sid}")
        if res['status'] == "Eligible":
            st.success("✅ ELIGIBLE TRACT")
        else:
            st.info("⚪ INELIGIBLE TRACT")
        st.write(f"**Parish:** {str(res['parish']).title()}")
        st.metric("Poverty Rate", f"{res.get('estimate!!percent below poverty level!!population for whom poverty status is determined', 'N/A')}")
    else:
        st.info("Click a tract to view the Opportunity Zone 2.0 profile.")