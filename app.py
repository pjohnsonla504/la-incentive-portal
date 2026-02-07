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

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master Data
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    
    # Mapping the long headers you provided to clean variables
    # Add or adjust these if the CSV spelling differs slightly
    column_mapping = {
        'Geography11-digit FIPS Code': 'GEOID',
        'Parish': 'parish',
        'Region': 'region',
        'Estimate!!Percent below poverty level!!Population for whom poverty status is determined': 'poverty_rate',
        'Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)': 'med_income',
        'Estimate!!Total!!Population for whom poverty status is determined': 'pop_total',
        'Opportunity Zones Insiders Eligibilty': 'is_eligible'
    }
    df = df.rename(columns=column_mapping)
    
    # Cleanup GEOID (Ensure 11 digits)
    df['GEOID'] = df['GEOID'].astype(str).str.extract(r'(\d{11}$)')
    
    # Clean Eligibility column (Convert "Yes"/"No" or 1/0 to integer 1 or 0)
    if 'is_eligible' in df.columns:
        df['is_eligible'] = df['is_eligible'].apply(lambda x: 1 if str(x).strip().lower() in ['yes', '1', '1.0', 'true'] else 0)
    else:
        df['is_eligible'] = 0

    # Load GeoJSON (Ensure you have this file in your repo)
    with open("la_tracts_2024.json") as f: 
        la_geojson = json.load(f)
        
    return df, la_geojson

master_df, la_geojson = load_data()

# User Filtering (Region/Parish assignment)
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    # Matches assigned value (e.g., 'Region 1' or 'Acadia Parish') against the data
    master_df = master_df[master_df[st.session_state["a_type"].lower()] == st.session_state["a_val"]]

# --- INTERFACE ---
st.title(f"📍 OZ 2.0 Master Eligibility Portal")
st.markdown("### Green = Eligible | Grey = Ineligible")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    # Parish Filter
    p_list = sorted(master_df['parish'].dropna().unique().tolist())
    sel_p = st.selectbox("Select Parish", ["All Parishes"] + p_list)
    m_df = master_df.copy()
    if sel_p != "All Parishes": 
        m_df = m_df[m_df['parish'] == sel_p]

    # Map highlighting logic
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="is_eligible", 
        color_continuous_scale=[(0, "#D3D3D3"), (1, "#28a745")], # Grey to Green
        range_color=[0, 1],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, hover_data=["GEOID", "poverty_rate", "med_income"]
    )
    fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')
    
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state["selected_tract"] = map_event["selection"]["points"][0]["location"]

with c2:
    sid = st.session_state["selected_tract"]
    row = master_df[master_df['GEOID'] == sid]
    
    if not row.empty:
        r = row.iloc[0]
        st.subheader(f"Tract: {sid}")
        st.write(f"**Parish:** {r['parish']} | **Region:** {r['region']}")
        
        # Display Eligibility Status
        if r['is_eligible'] == 1:
            st.success("✅ ELIGIBLE FOR OZ 2.0")
        else:
            st.error("❌ NOT ELIGIBLE")

        st.divider()
        st.metric("Poverty Rate", f"{r.get('poverty_rate', 0):.1f}%")
        st.metric("Median Income", f"${r.get('med_income', 0):,.0f}")
        
        # Recommendation Form
        with st.form("nomination"):
            cat = st.selectbox("Development Priority", ["Housing", "Industrial", "Mixed-Use", "Retail"])
            notes = st.text_area("Justification for State Nomination")
            if st.form_submit_button("Submit Nomination"):
                # Save logic here
                st.success("Nomination recorded.")
    else:
        st.info("Click a green tract on the map to begin the nomination process.")