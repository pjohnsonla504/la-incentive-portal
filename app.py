import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import os
import re
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

# --- DATA LOADING (STRICT JOIN VERSION) ---
@st.cache_data(ttl=60)
def load_data():
    csv_path = os.path.join(curr_dir, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(curr_dir, "la_tracts_2024.json")
    json_fallback = os.path.join(curr_dir, "tl_2025_22_tract.json")

    # 1. Load GeoJSON & Normalize Map Keys
    f_path = json_path if os.path.exists(json_path) else json_fallback
    with open(f_path) as f: 
        la_geojson = json.load(f)

    # Force all GeoJSON IDs to be exactly the last 11 digits found in the string
    for feature in la_geojson['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        clean_id = "".join(re.findall(r'\d+', raw_id))[-11:]
        feature['properties']['GEOID_CLEAN'] = clean_id

    # 2. Load CSV & Normalize Data Keys
    raw_df = pd.read_csv(csv_path)
    # Column B is always index 1
    raw_df.rename(columns={raw_df.columns[1]: 'raw_geoid'}, inplace=True)
    raw_df.columns = raw_df.columns.str.strip().str.lower()
    
    # Clean the CSV GEOID to be exactly 11 digits
    raw_df['geoid_clean'] = raw_df['raw_geoid'].astype(str).apply(lambda x: "".join(re.findall(r'\d+', x))[-11:])
    
    # 3. Rename Critical Columns
    mapping = {
        'parish': 'parish',
        'region': 'region',
        'estimate!!percent below poverty level!!population for whom poverty status is determined': 'poverty_rate',
        'estimate!!median family income in the past 12 months (in 2024 inflation-adjusted dollars)': 'med_income',
        'opportunity zones insiders eligibilty': 'is_eligible'
    }
    raw_df = raw_df.rename(columns=mapping)

    # 4. Master Join (Left join ensures all map shapes exist)
    all_map_ids = [f['properties']['GEOID_CLEAN'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_clean': all_map_ids})
    
    df = pd.merge(map_df, raw_df, on='geoid_clean', how='left')
    
    # 5. Final Categorization Logic (The "Green" Switch)
    def categorize(val):
        v = str(val).strip().lower()
        if v in ['yes', '1', '1.0', 'true', 'eligible']:
            return "Eligible"
        return "Ineligible"
    
    df['status'] = df['is_eligible'].apply(categorize)
    
    # Numeric cleanup
    df['poverty_rate'] = pd.to_numeric(df['poverty_rate'], errors='coerce').fillna(0)
    df['med_income'] = pd.to_numeric(df['med_income'], errors='coerce').fillna(0)
    df['parish'] = df['parish'].fillna("Louisiana")
        
    return df, la_geojson

master_df, la_geojson = load_data()

# --- INTERFACE ---
st.title("📍 OZ 2.0 Master Eligibility Portal")

# Sidebar Stats for Verification
eligible_count = len(master_df[master_df['status'] == "Eligible"])
st.sidebar.metric("Eligible Tracts Found", eligible_count)

c1, c2 = st.columns([0.6, 0.4])

with c1:
    m_df = master_df.copy()
    
    # User Filtering
    a_type = st.session_state["a_type"].lower()
    if st.session_state["role"].lower() != "admin" and a_type != "all":
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

    # Parish Filter
    p_list = sorted([p for p in m_df['parish'].unique() if p != "Louisiana"])
    sel_p = st.selectbox("Select Parish", ["Show All"] + p_list)
    if sel_p != "Show All": 
        m_df = m_df[m_df['parish'] == sel_p]

    # Optimized Map
    fig = px.choropleth_mapbox(
        m_df, 
        geojson=la_geojson, 
        locations="geoid_clean", 
        featureidkey="properties.GEOID_CLEAN", # Join on our new clean key
        color="status",
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#D3D3D3"},
        category_orders={"status": ["Eligible", "Ineligible"]},
        mapbox_style="carto-positron", 
        zoom=6, 
        center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, 
        hover_data=["geoid_clean", "parish", "poverty_rate"]
    )
    
    fig.update_layout(height=750, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state["selected_tract"] = map_event["selection"]["points"][0]["location"]

with c2:
    sid = st.session_state["selected_tract"]
    row = master_df[master_df['geoid_clean'] == sid]
    
    if not row.empty:
        r = row.iloc[0]
        st.subheader(f"Tract Profile: {sid}")
        
        if r['status'] == "Eligible":
            st.success("✅ QUALIFIED FOR OZ 2.0")
        else:
            st.info("⚪ STATUS: INELIGIBLE")

        st.divider()
        st.write(f"**Parish:** {str(r['parish']).title()}")
        st.metric("Poverty Rate", f"{r['poverty_rate']:.1f}%")
        st.metric("Median Family Income", f"${r['med_income']:,.0f}")
    else:
        st.info("Click any tract to view eligibility details.")