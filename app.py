import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import os
import re
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="OZ 2.0 Strategic Command", layout="wide")

# Initialize Session State
if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- 2. AUTHENTICATION ---
# (Using your provided GSheets logic)
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Recommendation Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in, p_in = st.text_input("Username").strip(), st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    db = conn.read(worksheet="Users", ttl=0)
                    db.columns = [c.strip() for c in db.columns]
                    match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                    if not match.empty:
                        st.session_state.update({
                            "authenticated": True, "username": u_in, 
                            "role": str(match.iloc[0]['Role']), 
                            "a_type": str(match.iloc[0]['Assigned_Type']), 
                            "a_val": str(match.iloc[0]['Assigned_Value'])
                        })
                        st.rerun()
                    else: st.error("Invalid credentials.")
                except Exception as e: st.error(f"Auth Error: {e}")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Primary Data File
    m = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    m.columns = [c.strip() for c in m.columns]
    
    # Identify GEOID Column (Column B / Index 1)
    geoid_col = m.columns[1]
    m['GEOID'] = m[geoid_col].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Standardize column names to lowercase for logic consistency
    m.columns = m.columns.str.strip().str.lower()
    
    # TRACT RECOMMENDATION LOGIC
    def categorize(row):
        # Column Q: opportunity zones insiders eligibilty
        # Column P: 5-year acs eligiblity
        is_rec = str(row.get('opportunity zones insiders eligibilty', '')).lower().strip() in ['yes', '1', 'true', 'eligible']
        is_elig = str(row.get('5-year acs eligiblity', '')).lower().strip() in ['yes', '1', 'true', 'eligible']
        
        # Poverty Math Fallback
        try:
            pov_col = [c for c in m.columns if 'poverty level' in c][0]
            pov = float(str(row.get(pov_col, 0)).replace('%', ''))
        except: pov = 0
        
        if is_rec: return "Recommended"
        if is_elig or pov >= 20.0: return "Eligible"
        return "Ineligible"

    m['status_detailed'] = m.apply(categorize, axis=1)

    # Load GeoJSON
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    return m, g

master_df, la_geojson = load_data()

# Apply User Filters
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"].lower()] == st.session_state["a_val"]]

# --- 4. RECOMMENDATION COUNTER ---
st.title(f"📍 OZ 2.0 Command Center: {st.session_state['a_val']}")

total_eligible = len(master_df[master_df['status_detailed'] != "Ineligible"])
current_recs = len(master_df[master_df['status_detailed'] == "Recommended"])
rec_limit = int(total_eligible * 0.25)

# Progress Bar Rendering
usage_pct = min(current_recs / rec_limit, 1.0) if rec_limit > 0 else 0
st.markdown("### Recommendation Tracker")
c_prog, c_stat = st.columns([0.8, 0.2])
with c_prog:
    st.progress(usage_pct, text=f"{current_recs} Recommended of {rec_limit} Max Allowed (25% Budget)")
with c_stat:
    st.metric("Budget Remaining", rec_limit - current_recs)

st.divider()

# --- 5. MAIN INTERFACE (2/3 MAP, 1/3 PROFILE) ---
c_map, c_profile = st.columns([0.66, 0.33])

with c_map:
    # Color mapping for visibility
    color_map = {"Recommended": "#1E5631", "Eligible": "#74C365", "Ineligible": "#D3D3D3"}
    
    fig = px.choropleth_mapbox(
        master_df, geojson=la_geojson, locations="geoid", featureidkey="properties.GEOID_MATCH",
        color="status_detailed",
        color_discrete_map=color_map,
        category_orders={"status_detailed": ["Recommended", "Eligible", "Ineligible"]},
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, hover_data=["geoid", "parish", "region"]
    )
    fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", y=1.02))
    
    sel_pts = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if sel_pts and "selection" in sel_pts and sel_pts["selection"]["points"]:
        st.session_state["selected_tract"] = sel_pts["selection"]["points"][0].get("location")

with c_profile:
    st.subheader("Tract Analysis")
    sid = st.session_state["selected_tract"]
    
    if sid:
        res = master_df[master_df['geoid'] == sid].iloc[0]
        
        # Identification
        st.markdown(f"#### Tract: `{sid}`")
        st.write(f"**Parish:** {str(res.get('parish', 'N/A')).title()}")
        st.write(f"**Region:** {str(res.get('region', 'N/A')).upper()}")
        
        if res['status_detailed'] == "Recommended":
            st.success("✅ CURRENTLY RECOMMENDED")
        elif res['status_detailed'] == "Eligible":
            st.info("💡 ELIGIBLE FOR RECOMMENDATION")
            
        st.divider()
        
        # Demographics
        st.markdown("##### 📊 Demographic Snapshot")
        
        # Find Census columns dynamically
        pov_col = [c for c in master_df.columns if 'poverty level' in c]
        inc_col = [c for c in master_df.columns if 'median family income' in c]
        
        d1, d2 = st.columns(2)
        with d1:
            val_p = res[pov_col[0]] if pov_col else "N/A"
            st.metric("Poverty Rate", f"{val_p}")
        with d2:
            val_i = res[inc_col[0]] if inc_col else "N/A"
            st.metric("Median Income", val_i)
            
        # Optional: Detailed list of other factors
        with st.expander("View Full Metrics"):
            st.write(res.to_frame().T)
    else:
        st.info("Click a census tract on the map to view demographics and recommendation status.")