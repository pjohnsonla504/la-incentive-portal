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

# --- 5. DATA LOADING (UPDATED FILENAME) ---
@st.cache_data(ttl=60)
def load_data():
    # Corrected filenames based on your GitHub repo
    json_filename = "tl_2025_22_tract.json"
    csv_filename = "Opportunity Zones 2.0 - Master Data File.csv"

    # Load GeoJSON
    try:
        with open(json_filename, "r") as f:
            la_geojson = json.load(f)
    except FileNotFoundError:
        st.error(f"⚠️ File Not Found: {json_filename}. Please ensure it is in the root folder of your GitHub repo.")
        st.stop()

    for feature in la_geojson['features']:
        # TIGER/Line files usually store the 11-digit code in 'GEOID' or 'GEOIDFQ'
        raw_id = str(feature['properties'].get('GEOID', ''))
        # Standardize to last 11 digits to ensure match with CSV FIPS
        feature['properties']['GEOID_CLEAN'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Load CSV
    try:
        df = pd.read_csv(csv_filename)
    except FileNotFoundError:
        st.error(f"⚠️ File Not Found: {csv_filename}")
        st.stop()

    # Column B (Index 1) is the 11-digit FIPS code
    df.rename(columns={df.columns[1]: 'raw_geoid'}, inplace=True)
    df.columns = df.columns.str.strip().str.lower()
    df['geoid_clean'] = df['raw_geoid'].astype(str).apply(lambda x: "".join(re.findall(r'\d+', x))[-11:])
    
    # 620-Tract Eligibility Logic
    def get_status(row):
        # Checks Column Q (Insiders) and Column P (ACS)
        insider = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip()
        acs = str(row.get('5-year acs eligiblity', '')).lower().strip()
        
        # Poverty threshold logic (Column headers often have '!!' from Census)
        try:
            pov_col = [c for c in df.columns if 'poverty level' in c][0]
            pov = float(str(row.get(pov_col, 0)).replace('%', ''))
        except: pov = 0
        
        # Highlight if explicitly listed or if meeting poverty criteria
        if any(x in ['yes', '1', 'true', 'eligible'] for x in [insider, acs]) or pov >= 20.0:
            return "Eligible"
        return "Ineligible"

    df['status'] = df.apply(get_status, axis=1)
    
    # Merge map and data
    all_map_ids = [f['properties']['GEOID_CLEAN'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_clean': all_map_ids})
    merged = pd.merge(map_df, df, on='geoid_clean', how='left').fillna({'status': 'Ineligible', 'parish': 'Unknown'})
    return merged, la_geojson

master_df, la_geojson = load_data()

# --- 6. DASHBOARD ---
st.title("📍 Louisiana OZ 2.0: Master Eligibility Portal")
st.sidebar.metric("Highlighted Eligible Tracts", len(master_df[master_df['status'] == "Eligible"]))

# Filter based on Assigned_Value / Role
m_df = master_df.copy()
if st.session_state["role"].lower() != "admin":
    a_type = st.session_state["a_type"].lower()
    if a_type in m_df.columns:
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

c1, c2 = st.columns([0.65, 0.35])

with c1:
    fig = px.choropleth_mapbox(
        m_df, 
        geojson=la_geojson, 
        locations="geoid_clean", 
        featureidkey="properties.GEOID_CLEAN",
        color="status",
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#D3D3D3"},
        category_orders={"status": ["Eligible", "Ineligible"]},
        mapbox_style="carto-positron", 
        zoom=6, 
        center={"lat": 30.9, "lon": -91.9},
        opacity=0.6, 
        hover_data=["geoid_clean", "parish"]
    )
    fig.update_layout(height=750, margin={"r":0,"t":0,"l":0,"b":0})
    
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if selected and "selection" in selected and selected["selection"]["points"]:
        st.session_state["selected_tract"] = selected["selection"]["points"][0]["location"]

with c2:
    sid = st.session_state["selected_tract"]
    if sid:
        res = master_df[master_df['geoid_clean'] == sid].iloc[0]
        st.header(f"Tract {sid}")
        if res['status'] == "Eligible":
            st.success("✅ ELIGIBLE TRACT")
        else:
            st.info("⚪ INELIGIBLE TRACT")
        
        st.write(f"**Parish:** {str(res['parish']).title()}")
        # Display the poverty rate if available
        pov_col = [c for c in master_df.columns if 'poverty level' in c]
        if pov_col:
            st.metric("Poverty Rate", f"{res.get(pov_col[0], 'N/A')}")
    else:
        st.info("Click a green or grey tract on the map to view the economic profile.")