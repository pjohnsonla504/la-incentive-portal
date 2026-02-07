import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import os
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="OZ 2.0 Strategic Command", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- 2. DATA LOADING & PROCESSING ---
@st.cache_data(ttl=60)
def load_data():
    # Primary Data File
    csv_filename = "Opportunity Zones 2.0 - Master Data File.csv"
    try:
        m = pd.read_csv(csv_filename)
    except FileNotFoundError:
        st.error(f"File not found: {csv_filename}")
        st.stop()

    # Identify GEOID Column (Column B / Index 1)
    geoid_col_raw = m.columns[1]
    m['GEOID_KEY'] = m[geoid_col_raw].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Clean column names for consistent logic
    m.columns = m.columns.str.strip().str.lower()
    
    # Identify Census Headers dynamically
    pov_cols = [c for c in m.columns if 'percent' in c and 'poverty level' in c]
    inc_cols = [c for c in m.columns if 'median' in c and 'family income' in c]
    
    # Standardizing numeric data for eligibility math
    if pov_cols:
        m['poverty_rate_clean'] = pd.to_numeric(m[pov_cols[0]].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    else:
        m['poverty_rate_clean'] = 0

    # TRACT CATEGORIZATION LOGIC (The 25% budget logic)
    def categorize(row):
        # Column Q: opportunity zones insiders eligibilty
        # Column P: 5-year acs eligiblity
        is_rec = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip() in ['yes', '1', 'true', 'eligible']
        is_elig = str(row.get('5-year acs eligiblity', '')).lower().strip() in ['yes', '1', 'true', 'eligible']
        
        if is_rec: return "Recommended"
        if is_elig or row.get('poverty_rate_clean', 0) >= 20.0: return "Eligible"
        return "Ineligible"

    m['status_detailed'] = m.apply(categorize, axis=1)

    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    return m, g, pov_cols, inc_cols

master_df, la_geojson, POV_HEADER, INC_HEADER = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in, p_in = st.text_input("Username").strip(), st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = [c.strip() for c in db.columns]
                match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True, "username": u_in, 
                        "role": str(match.iloc[0]['Role']), 
                        "a_type": str(match.iloc[0]['Assigned_Type']).lower(), 
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# Filter Data by User Assignment
m_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    target_col = st.session_state["a_type"]
    if target_col in m_df.columns:
        m_df = m_df[m_df[target_col].astype(str) == st.session_state["a_val"]]

# --- 4. RECOMMENDATION COUNTER ---
total_eligible = len(m_df[m_df['status_detailed'] != "Ineligible"])
recommended_count = len(m_df[m_df['status_detailed'] == "Recommended"])
rec_cap = int(total_eligible * 0.25)

st.title(f"📍 OZ 2.0 Strategic Command: {st.session_state['a_val']}")

# Progress Bar Rendering
usage_pct = min(1.0, recommended_count / rec_cap) if rec_cap > 0 else 0
st.markdown("### Recommendation Tracker")
c_prog, c_stat = st.columns([0.8, 0.2])
with c_prog:
    st.progress(usage_pct, text=f"{recommended_count} Recommended of {rec_cap} Allocated Budget (25%)")
with c_stat:
    st.metric("Budget Remaining", max(0, rec_cap - recommended_count))

st.divider()

# --- 5. MAIN INTERFACE (2/3 MAP, 1/3 PROFILE) ---
col_left, col_right = st.columns([0.66, 0.33])

with col_left:
    color_map = {"Recommended": "#1E5631", "Eligible": "#74C365", "Ineligible": "#D3D3D3"}
    
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid_key", featureidkey="properties.GEOID_MATCH",
        color="status_detailed",
        color_discrete_map=color_map,
        category_orders={"status_detailed": ["Recommended", "Eligible", "Ineligible"]},
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, hover_data=["geoid_key", "parish"]
    )
    fig.update_layout(height=750, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", y=1.02, x=1, xanchor="right"))
    
    # FIXED SELECTION SYNTAX
    sel_pts = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if sel_pts and sel_pts.get("selection") and sel_pts["selection"].get("points"):
        st.session_state["selected_tract"] = sel_pts["selection"]["points"][0].get("location")

with col_right:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    
    if sid:
        # Locate the row in the master dataframe
        res = master_df[master_df['geoid_key'] == sid].iloc[0]
        
        # Identification
        st.markdown(f"#### Tract ID: `{sid}`")
        st.write(f"**Parish:** {str(res.get('parish', 'N/A')).title()}")
        st.write(f"**Status:** {res['status_detailed']}")
        
        st.divider()
        
        # Demographics
        st.markdown("##### 📊 Demographic Snapshot")
        d1, d2 = st.columns(2)
        with d1:
            p_val = res[POV_HEADER[0]] if POV_HEADER else "N/A"
            st.metric("Poverty Rate", p_val)
        with d2:
            i_val = res[INC_HEADER[0]] if INC_HEADER else "N/A"
            st.metric("Median Income", i_val)
            
        st.write("---")
        st.caption("Data: 2026 OZ 2.0 Master File")
    else:
        st.info("Click a census tract on the map to view detailed demographics.")