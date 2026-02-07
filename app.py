# --- 1. IMPORTS ---
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from streamlit_gsheets import GSheetsConnection

# --- 2. PAGE CONFIG ---
st.set_page_config(page_title="LA OZ 2.0 Strategic Command", layout="wide")

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
                else: st.error("Invalid credentials")
            except Exception as e: st.error(f"Login Error: {e}")
    st.stop()

# --- 5. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    json_filename = "tl_2025_22_tract.json"
    csv_filename = "Opportunity Zones 2.0 - Master Data File.csv"

    # Load GeoJSON
    with open(json_filename, "r") as f:
        la_geojson = json.load(f)
    for feature in la_geojson['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Load CSV
    df = pd.read_csv(csv_filename)
    df.rename(columns={df.columns[1]: 'fips_code'}, inplace=True)
    df.columns = df.columns.str.strip().str.lower()
    df['geoid_match'] = df['fips_code'].astype(str).apply(lambda x: "".join(re.findall(r'\d+', x)).zfill(11)[-11:])
    
    # Categorization
    def categorize_tract(row):
        # Column Q: The Recommendation Flag
        is_rec = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip() in ['yes', '1', 'true', 'eligible']
        # Column P: ACS Eligibility
        is_elig = str(row.get('5-year acs eligiblity', '')).lower().strip() in ['yes', '1', 'true', 'eligible']
        
        if is_rec: return "Recommended"
        if is_elig: return "Eligible"
        return "Ineligible"

    df['status_detailed'] = df.apply(categorize_tract, axis=1)

    # Master Join
    map_ids = [f['properties']['GEOID_MATCH'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_match': map_ids})
    merged = pd.merge(map_df, df, on='geoid_match', how='left').fillna({'status_detailed': 'Ineligible', 'parish': 'Unknown', 'region': 'Unknown'})
    
    return merged, la_geojson

master_df, la_geojson = load_data()

# --- 6. TOP SECTION: RECOMMENDATION COUNTER ---
st.title("📍 Louisiana OZ 2.0 Strategic Command")

# Calculate metrics
total_eligible = len(master_df[master_df['status_detailed'] != "Ineligible"])
recommended_count = len(master_df[master_df['status_detailed'] == "Recommended"])
rec_cap = int(total_eligible * 0.25)

# Rendering the Recommendation Counter Visualization
st.markdown(f"### Recommendation Tracker")
prog_cols = st.columns([0.8, 0.2])
with prog_cols[0]:
    # Tracks how many are recommended vs the 25% guideline
    progress_val = min(recommended_count / rec_cap, 1.0) if rec_cap > 0 else 0
    st.progress(progress_val, text=f"{recommended_count} Recommended of {rec_cap} Allowed (25% Threshold)")
with prog_cols[1]:
    st.metric("Budget Remaining", rec_cap - recommended_count)

st.divider()

# --- 7. MAIN INTERFACE (2/3 MAP, 1/3 PROFILE) ---
col_left, col_right = st.columns([0.66, 0.33])

with col_left:
    # Map Filtering
    m_df = master_df.copy()
    if st.session_state["role"].lower() != "admin":
        a_type = st.session_state["a_type"].lower()
        if a_type in m_df.columns:
            m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

    color_map = {"Recommended": "#1E5631", "Eligible": "#74C365", "Ineligible": "#D3D3D3"}

    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid_match", featureidkey="properties.GEOID_MATCH",
        color="status_detailed",
        color_discrete_map=color_map,
        category_orders={"status_detailed": ["Recommended", "Eligible", "Ineligible"]},
        mapbox_style="carto-positron", zoom=6, center={"lat": 30.9, "lon": -91.9},
        opacity=0.7, hover_data=["geoid_match", "parish"]
    )
    fig.update_layout(height=750, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    
    # Event selection
    map_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_data and "selection" in map_data and map_data["selection"]["points"]:
        st.session_state["selected_tract"] = map_data["selection"]["points"][0]["location"]

with col_right:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    
    if sid:
        res = master_df[master_df['geoid_match'] == sid].iloc[0]
        
        # Part A: Core Identification
        st.markdown(f"#### Tract ID: `{sid}`")
        st.write(f"**Parish:** {str(res['parish']).title()}")
        st.write(f"**Region:** {str(res['region']).upper()}")
        
        if res['status_detailed'] == "Recommended":
            st.success("✅ CURRENTLY RECOMMENDED")
        elif res['status_detailed'] == "Eligible":
            st.info("💡 ELIGIBLE FOR RECOMMENDATION")
        
        st.divider()
        
        # Part B: Tract Demographics
        st.markdown("##### 📊 Demographic Snapshot")
        
        # Dynamically pulling demographics based on census column names
        pov_col = [c for c in master_df.columns if 'poverty level' in c]
        inc_col = [c for c in master_df.columns if 'median family income' in c]
        
        c1, c2 = st.columns(2)
        with c1:
            val_p = res[pov_col[0]] if pov_col else "N/A"
            st.metric("Poverty Rate", f"{val_p}")
        with c2:
            val_i = res[inc_col[0]] if inc_col else "N/A"
            # Format as currency if it's a number
            try:
                formatted_inc = f"${float(val_i):,.0f}"
            except:
                formatted_inc = val_i
            st.metric("Median Income", formatted_inc)
            
        # Placeholder for more demographics (Education, Race, etc.)
        st.write("---")
        st.caption("Detailed demographic data sourced from 2020-2024 ACS Estimates.")
        
    else:
        st.info("Click a tract on the map to view detailed demographics and recommendation status.")