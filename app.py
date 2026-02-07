# --- 1. IMPORTS ---
import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import re
from streamlit_gsheets import GSheetsConnection

# --- 2. PAGE CONFIG ---
st.set_page_config(page_title="LA OZ 2.0 Strategy Portal", layout="wide")

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
    
    # 25% Logic Categorization
    def categorize_tract(row):
        # Column Q: The user's active recommendations
        q_val = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip()
        # Column P: The broader eligible pool
        p_val = str(row.get('5-year acs eligiblity', '')).lower().strip()
        
        is_nominated = q_val in ['yes', '1', 'true', 'eligible']
        is_eligible = p_val in ['yes', '1', 'true', 'eligible']
        
        if is_nominated:
            return "Recommended (Within 25%)"
        elif is_eligible:
            return "Eligible for Recommendation"
        else:
            return "Ineligible"

    df['status_detailed'] = df.apply(categorize_tract, axis=1)

    # Master Join
    map_ids = [f['properties']['GEOID_MATCH'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid_match': map_ids})
    merged = pd.merge(map_df, df, on='geoid_match', how='left').fillna({'status_detailed': 'Ineligible', 'parish': 'Unknown'})
    
    return merged, la_geojson

master_df, la_geojson = load_data()

# --- 6. TOP SECTION: THE 25% PROGRESS BAR ---
st.title("📍 OZ 2.0 Strategic Planner")

# Calculate the Budget (25% of Eligible Universe)
eligible_pool = master_df[master_df['status_detailed'] != "Ineligible"]
total_eligible_count = len(eligible_pool)
current_recommendations = len(master_df[master_df['status_detailed'] == "Recommended (Within 25%)"])

# Define the Cap (25%)
recommendation_cap = int(total_eligible_count * 0.25)
usage_pct = min(current_recommendations / recommendation_cap, 1.0) if recommendation_cap > 0 else 0

# Display Visualization
st.subheader("Nomination Capacity")
cols = st.columns([0.7, 0.3])
with cols[0]:
    # Dynamic Progress Bar
    bar_color = "green" if usage_pct < 0.9 else "orange" if usage_pct <= 1.0 else "red"
    st.progress(usage_pct, text=f"{current_recommendations} of {recommendation_cap} Maximum Nominations Used")
with cols[1]:
    remaining = recommendation_cap - current_recommendations
    st.metric("Remaining Budget", f"{remaining} Tracts", delta_color="normal")

st.divider()

# --- 7. THE MAP ---
# User Filtering (Admin vs Restricted)
m_df = master_df.copy()
if st.session_state["role"].lower() != "admin":
    a_type = st.session_state["a_type"].lower()
    if a_type in m_df.columns:
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

# Color Map: Highlighting Recommended vs Eligible
color_map = {
    "Recommended (Within 25%)": "#1E5631",    # Dark Green
    "Eligible for Recommendation": "#74C365", # Light Green
    "Ineligible": "#D3D3D3"                   # Grey
}

fig = px.choropleth_mapbox(
    m_df, 
    geojson=la_geojson, 
    locations="geoid_match", 
    featureidkey="properties.GEOID_MATCH",
    color="status_detailed",
    color_discrete_map=color_map,
    category_orders={"status_detailed": ["Recommended (Within 25%)", "Eligible for Recommendation", "Ineligible"]},
    mapbox_style="carto-positron", 
    zoom=6, center={"lat": 30.9, "lon": -91.9},
    opacity=0.7, 
    hover_data=["geoid_match", "parish"]
)
fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))

st.plotly_chart(fig, use_container_width=True, on_select="rerun")

# --- 8. SELECTION DETAILS ---
sid = st.session_state["selected_tract"]
if sid:
    res = master_df[master_df['geoid_match'] == sid].iloc[0]
    with st.expander(f"Tract {sid} Profile", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("Status", res['status_detailed'])
        c2.metric("Parish", str(res['parish']).title())
        # Example metric (update with your actual column names if different)
        c3.metric("Poverty Rate", f"{res.get('estimate!!percent below poverty level!!population for whom poverty status is determined', 'N/A')}")