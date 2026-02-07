import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login"):
        u_in, p_in = st.text_input("User").strip(), st.text_input("Pass", type="password").strip()
        if st.form_submit_button("Access"):
            db = conn.read(worksheet="Users", ttl=0)
            db.columns = [c.strip() for c in db.columns]
            match = db[(db['Username'].astype(str)==u_in) & (db['Password'].astype(str)==p_in)]
            if not match.empty:
                st.session_state.update({"authenticated": True, "username": u_in, "role": str(match.iloc[0]['Role']), 
                                        "a_type": str(match.iloc[0]['Assigned_Type']), "a_val": str(match.iloc[0]['Assigned_Value'])})
                st.rerun()
    st.stop()

# --- DATA LOADING (POSITIONAL INDEX VERSION) ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master Data
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    
    # STEP 1: Positional Renaming (Column B is Index 1)
    # We rename the column at index 1 to 'geoid' so the rest of the script can find it
    df.rename(columns={df.columns[1]: 'geoid'}, inplace=True)
    
    # STEP 2: Normalize all other column names to lowercase for safety
    df.columns = df.columns.str.strip().str.lower()
    
    # STEP 3: Map the long Eligibility and Demographics headers
    column_mapping = {
        'parish': 'parish',
        'region': 'region',
        'estimate!!percent below poverty level!!population for whom poverty status is determined': 'poverty_rate',
        'estimate!!median family income in the past 12 months (in 2024 inflation-adjusted dollars)': 'med_income',
        'opportunity zones insiders eligibilty': 'is_eligible'
    }
    df = df.rename(columns=column_mapping)

    # Cleanup geoid (Ensure it's a clean 11-digit string)
    df['geoid'] = df['geoid'].astype(str).str.extract(r'(\d{11}$)')
    
    # Handle missing or malformed eligibility flags
    if 'is_eligible' in df.columns:
        df['is_eligible'] = df['is_eligible'].apply(lambda x: 1 if str(x).strip().lower() in ['yes', '1', '1.0', 'true'] else 0)
    else:
        df['is_eligible'] = 0

    # Load GeoJSON
    with open("la_tracts_2024.json") as f: 
        la_geojson = json.load(f)
        
    return df, la_geojson

master_df, la_geojson = load_data()

# --- FILTERING ---
a_type = st.session_state["a_type"].lower()
if st.session_state["role"].lower() != "admin" and a_type != "all":
    master_df = master_df[master_df[a_type] == st.session_state["a_val"]]

# --- INTERFACE ---
st.title(f"📍 OZ 2.0 Master Data View")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    p_list = sorted(master_df['parish'].dropna().unique().tolist())
    sel_p = st.selectbox("Select Parish", ["All Parishes"] + p_list)
    m_df = master_df.copy()
    if sel_p != "All Parishes": 
        m_df = m_df[m_df['parish'] == sel_p]

    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid", featureidkey="properties.GEOID",
        color="is_eligible", 
        color_continuous_scale=[(0, "#D3D3D3"), (1, "#28a745")],
        range_color=[0, 1],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, hover_data=["geoid", "poverty_rate", "med_income"]
    )
    fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')
    
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state["selected_tract"] = map_event["selection"]["points"][0]["location"]

with c2:
    sid = st.session_state["selected_tract"]
    row = master_df[master_df['geoid'] == sid]
    
    if not row.empty:
        r = row.iloc[0]
        st.subheader(f"Tract: {sid}")
        st.write(f"**Parish:** {r['parish'].title()} | **Region:** {r['region']}")
        
        # Color-coded status header
        if r['is_eligible'] == 1:
            st.success("✅ ELIGIBLE FOR OZ 2.0")
        else:
            st.error("❌ NOT ELIGIBLE")

        st.divider()
        # Metrics using mapped variables
        st.metric("Poverty Rate", f"{float(r.get('poverty_rate', 0)):.1f}%")
        st.metric("Median Family Income", f"${float(r.get('med_income', 0)):,.0f}")
    else:
        st.info("Click a tract on the map to view detailed eligibility data.")