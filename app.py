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

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    csv_path = os.path.join(curr_dir, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(curr_dir, "la_tracts_2024.json")
    json_fallback = os.path.join(curr_dir, "tl_2025_22_tract.json")

    # Load GeoJSON
    f_path = json_path if os.path.exists(json_path) else json_fallback
    with open(f_path) as f: 
        la_geojson = json.load(f)

    all_geoids = [f['properties']['GEOID'] for f in la_geojson['features']]
    map_df = pd.DataFrame({'geoid': all_geoids})

    # Load CSV
    raw_df = pd.read_csv(csv_path)
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
    
    # Merge and Clean
    df = pd.merge(map_df, raw_df, on='geoid', how='left')
    
    # --- CRITICAL FIX FOR GREEN HIGHLIGHTING ---
    # Convert the raw data into specific string categories for Plotly
    def categorize_eligibility(val):
        if str(val).strip().lower() in ['yes', '1', '1.0', 'true']:
            return "Eligible"
        return "Ineligible"
    
    df['status'] = df['is_eligible'].apply(categorize_eligibility)
    
    # Fill remaining columns
    df['poverty_rate'] = pd.to_numeric(df['poverty_rate'], errors='coerce').fillna(0)
    df['med_income'] = pd.to_numeric(df['med_income'], errors='coerce').fillna(0)
    df['parish'] = df['parish'].fillna("Unknown")
        
    return df, la_geojson

master_df, la_geojson = load_data()

# --- INTERFACE ---
st.title(f"📍 OZ 2.0 - Master Eligibility Map")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    m_df = master_df.copy()
    
    # User Assignment Filtering
    a_type = st.session_state["a_type"].lower()
    if st.session_state["role"].lower() != "admin" and a_type != "all":
        m_df = m_df[m_df[a_type] == st.session_state["a_val"]]

    # Parish Filter
    p_list = sorted(m_df['parish'].unique().tolist())
    sel_p = st.selectbox("Select Parish", ["Louisiana (All)"] + p_list)
    if sel_p != "Louisiana (All)": 
        m_df = m_df[m_df['parish'] == sel_p]

    # Map with Fixed Discrete Colors
    fig = px.choropleth_mapbox(
        m_df, 
        geojson=la_geojson, 
        locations="geoid", 
        featureidkey="properties.GEOID",
        color="status", # Using our string category
        color_discrete_map={
            "Eligible": "#28a745",   # Pure Green
            "Ineligible": "#D3D3D3"  # Light Grey
        },
        category_orders={"status": ["Eligible", "Ineligible"]}, # Sets legend order
        mapbox_style="carto-positron", 
        zoom=6, 
        center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, 
        hover_data=["geoid", "parish"]
    )
    
    fig.update_layout(
        height=700, 
        margin={"r":0,"t":0,"l":0,"b":0},
        legend=dict(title="OZ 2.0 Status", orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state["selected_tract"] = map_event["selection"]["points"][0]["location"]

with c2:
    sid = st.session_state["selected_tract"]
    row = master_df[master_df['geoid'] == sid]
    
    if not row.empty:
        r = row.iloc[0]
        st.subheader(f"Tract: {sid}")
        st.write(f"**Parish:** {str(r['parish']).title()}")
        
        if r['status'] == "Eligible":
            st.success("✅ ELIGIBLE FOR OPPORTUNITY ZONE 2.0")
        else:
            st.info("⚪ STATUS: INELIGIBLE")

        st.divider()
        st.metric("Poverty Rate", f"{r['poverty_rate']:.1f}%")
        st.metric("Median Family Income", f"${r['med_income']:,.0f}")
    else:
        st.info("Click any tract (Green or Grey) to view demographics.")