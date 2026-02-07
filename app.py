import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import os
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")
curr_dir = os.path.dirname(os.path.abspath(__file__))

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
                st.session_state.update({
                    "authenticated": True, "username": u_in, "role": str(match.iloc[0]['Role']), 
                    "a_type": str(match.iloc[0]['Assigned_Type']), "a_val": str(match.iloc[0]['Assigned_Value'])
                })
                st.rerun()
    st.stop()

# --- DATA LOADING (FULL-MAP CLICKABILITY VERSION) ---
@st.cache_data(ttl=60)
def load_data():
    csv_path = os.path.join(curr_dir, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(curr_dir, "la_tracts_2024.json")
    json_fallback = os.path.join(curr_dir, "tl_2025_22_tract.json")

    # A. Load GeoJSON first to get the "Master List" of all tracts
    final_json_path = json_path if os.path.exists(json_path) else json_fallback
    try:
        with open(final_json_path) as f: 
            la_geojson = json.load(f)
    except FileNotFoundError:
        st.error("GeoJSON file missing."); st.stop()

    # Create a DataFrame of every GEOID present in the map
    all_map_geoids = [f['properties']['GEOID'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid': all_map_geoids})

    # B. Load Master CSV Data
    try:
        raw_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        st.error("CSV Not Found."); st.stop()
    
    # C. Prepare CSV Data
    raw_df.rename(columns={raw_df.columns[1]: 'geoid'}, inplace=True)
    raw_df.columns = raw_df.columns.str.strip().str.lower()
    
    mapping = {
        'parish': 'parish',
        'region': 'region',
        'estimate!!percent below poverty level!!population for whom poverty status is determined': 'poverty_rate',
        'estimate!!median family income in the past 12 months (in 2024 inflation-adjusted dollars)': 'med_income',
        'opportunity zones insiders eligibilty': 'is_eligible'
    }
    raw_df = raw_df.rename(columns=mapping)
    raw_df['geoid'] = raw_df['geoid'].astype(str).str.extract(r'(\d{11}$)')
    
    # D. MERGE: Map + CSV (This makes every tract clickable)
    df = pd.merge(map_df, raw_df, on='geoid', how='left')

    # Fill NaNs for tracts not in the CSV
    df['is_eligible'] = df['is_eligible'].apply(lambda x: 1 if str(x).strip().lower() in ['yes', '1', '1.0', 'true'] else 0)
    df['poverty_rate'] = pd.to_numeric(df['poverty_rate'], errors='coerce').fillna(0)
    df['med_income'] = pd.to_numeric(df['med_income'], errors='coerce').fillna(0)
    df['parish'] = df['parish'].fillna("Unknown")
    df['region'] = df['region'].fillna("N/A")
        
    return df, la_geojson

master_df, la_geojson = load_data()

# --- INTERFACE ---
st.title(f"📍 OZ 2.0 - All Tract Explorer")
st.caption("Green: Eligible | Grey: Ineligible | All tracts are clickable for profiling.")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    # Filtering logic
    a_type = st.session_state["a_type"].lower()
    m_df = master_df.copy()
    if st.session_state["role"].lower() != "admin" and a_type != "all":
        # Keep all map tracts but filter the data overlay
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

    p_list = sorted(m_df['parish'].unique().tolist())
    sel_p = st.selectbox("Filter by Parish", ["All Louisiana"] + p_list)
    if sel_p != "All Louisiana": 
        m_df = m_df[m_df['parish'] == sel_p]

    # The Map
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid", featureidkey="properties.GEOID",
        color="is_eligible", 
        color_continuous_scale=[(0, "#D3D3D3"), (1, "#28a745")],
        range_color=[0, 1],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, hover_data=["geoid", "parish"]
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
        st.subheader(f"Tract Profile: {sid}")
        st.markdown(f"**Parish:** {str(r['parish']).title()}")
        
        # Display Status
        if r['is_eligible'] == 1:
            st.success("✅ ELIGIBLE FOR OPPORTUNITY ZONE 2.0")
        else:
            st.warning("⚪ INELIGIBLE / NOT DETERMINED")

        st.divider()
        st.metric("Poverty Rate", f"{r['poverty_rate']:.1f}%")
        st.metric("Median Family Income", f"${r['med_income']:,.0f}")
        
        st.info("Profiles are generated for all clicked tracts, regardless of eligibility status.")
    else:
        st.write("### ⬅️ Select any tract on the map")
        st.write("Clicking any region (Green or Grey) will load its profile data here.")