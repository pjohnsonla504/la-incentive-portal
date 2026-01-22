import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import json
import os
from datetime import datetime
from geopy.geocoders import Nominatim
from shapely.geometry import shape, Point

# 1. PAGE SETUP
st.set_page_config(page_title="Louisiana OZ & NMTC Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F8F9FA; color: #1E1E1E; }
    div[data-testid="stMetric"] { 
        background-color: #FFFFFF; border: 1px solid #DEE2E6;
        border-radius: 8px; padding: 10px !important;
        box-shadow: 0px 1px 3px rgba(0,0,0,0.05); margin-bottom: 10px;
    }
    .status-box {
        padding: 10px; border-radius: 8px; text-align: center;
        font-weight: 700; font-size: 1rem; margin-bottom: 15px;
        border: 1px solid rgba(0,0,0,0.1);
    }
    .status-deep-distress { background-color: #343a40; color: white; }
    .status-eligible { background-color: #D1E7DD; color: #0F5132; }
    .status-ineligible { background-color: #F8D7DA; color: #842029; }
    .main-title { color: #0D6EFD; font-weight: 800; font-size: 1.8rem; margin-bottom: 20px; }
    .submission-container { background-color: #FFFFFF; padding: 20px; border-radius: 10px; border: 1px solid #DEE2E6; margin-top: 15px; }
    </style>
    """, unsafe_allow_html=True)

# 2. DATA LOADING & ELIGIBILITY
@st.cache_data
def load_data():
    df = pd.read_csv("tract_data_final.csv")
    df.columns = df.columns.str.strip()
    
    # Cleaning Numeric Columns (G-M)
    for col in df.columns[6:13]:
        df[col] = pd.to_numeric(df[col].astype(str).str.replace(r'[$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # Restore Full List of Variable Mappings
    df = df.rename(columns={
        df.columns[0]: 'GEOID', 
        df.columns[6]: 'Total Population',           
        df.columns[7]: 'Median Household Income',    
        df.columns[8]: 'Poverty Rate',               
        df.columns[9]: 'Unemployment Rate',          
        df.columns[10]: 'Student Population',        
        df.columns[11]: 'High School Educated',      
        df.columns[12]: 'College Educated',          
        df.columns[14]: 'Parish',              
        df.columns[15]: 'REDO'                 
    })
    df['GEOID'] = df['GEOID'].astype(str).str.split('.').str[0].str.zfill(11)
    
    state_mfi = df['Median Household Income'].median()

    # NMTC Logic (Deep Distress Restore)
    def check_nmtc(row):
        is_deep = (row['Poverty Rate'] >= 30.0) or (row['Median Household Income'] <= (state_mfi * 0.60)) or (row['Unemployment Rate'] >= 9.0)
        is_basic = (row['Poverty Rate'] >= 20.0) or (row['Median Household Income'] <= (state_mfi * 0.80))
        if is_deep: return "Deeply Distressed"
        if is_basic: return "Eligible"
        return "Ineligible"

    # OZ 2.0 Logic
    def check_oz(row):
        if row['Median Household Income'] <= (state_mfi * 0.70): return "Eligible"
        if (row['Poverty Rate'] >= 20.0) and (row['Median Household Income'] <= (state_mfi * 1.25)): return "Eligible"
        return "Ineligible"
    
    df['NMTC_Status'] = df.apply(check_nmtc, axis=1)
    df['OZ_Status'] = df.apply(check_oz, axis=1)
    return df

@st.cache_data
def load_geojson():
    with open("tl_2025_22_tract.json") as f:
        return json.load(f)

df = load_data()
full_geo = load_geojson()

# 3. STATE MANAGEMENT
if 'active_geoid' not in st.session_state:
    st.session_state.active_geoid = df['GEOID'].iloc[0]

# 4. SIDEBAR
with st.sidebar:
    st.title("Filters")
    redo_list = ["Statewide"] + sorted(df['REDO'].unique().tolist())
    sel_redo = st.selectbox("REDO Region", redo_list)
    p_df = df[df['REDO'] == sel_redo] if sel_redo != "Statewide" else df
    sel_parish = st.selectbox("Parish", ["All Parishes"] + sorted(p_df['Parish'].unique().tolist()))

# 5. ISOLATION & ZOOM LOGIC
target_df = p_df.copy()
if sel_parish != "All Parishes":
    target_df = target_df[target_df['Parish'] == sel_parish]

valid_geoids = set(target_df['GEOID'].tolist())
isolated_features = [f for f in full_geo['features'] if f['properties']['GEOID'] in valid_geoids]
isolated_geo = {"type": "FeatureCollection", "features": isolated_features}

# 6. MAIN DASHBOARD LAYOUT
st.markdown("<h1 class='main-title'>Louisiana Investment Strategy Portal</h1>", unsafe_allow_html=True)
col_left, col_right = st.columns([7, 3]) 

# --- LEFT COLUMN: MAP & JUSTIFICATION ---
with col_left:
    m = folium.Map(tiles="CartoDB positron")
    
    def style_fn(feat):
        gid = feat['properties']['GEOID']
        match = df[df['GEOID'] == gid]
        if match.empty: return {'fillColor': '#CED4DA'}
        if gid == st.session_state.active_geoid:
            return {'fillColor': '#0D6EFD', 'fillOpacity': 0.8, 'color': 'black', 'weight': 4}
        # Tracks highlighted green are only those eligible for Opportunity Zone 2.0
        fill = '#198754' if match['OZ_Status'].values[0] == "Eligible" else '#CED4DA'
        return {'fillColor': fill, 'fillOpacity': 0.5, 'color': 'gray', 'weight': 1}

    geo_layer = folium.GeoJson(isolated_geo, style_function=style_fn)
    geo_layer.add_to(m)
    
    if isolated_features:
        m.fit_bounds(geo_layer.get_bounds())

    map_output = st_folium(m, use_container_width=True, height=600, key="main_map")
    
    if map_output['last_active_drawing']:
        clicked_geoid = map_output['last_active_drawing']['properties']['GEOID']
        if clicked_geoid != st.session_state.active_geoid:
            st.session_state.active_geoid = clicked_geoid
            st.rerun()

    # RESTORED: Tract Recommendation Below Map
    current_tract = df[df['GEOID'] == st.session_state.active_geoid].iloc[0]
    st.markdown('<div class="submission-container">', unsafe_allow_html=True)
    st.subheader(f"🎯 Recommendation: Tract {st.session_state.active_geoid}")
    justification = st.text_area("Justification Text Box", placeholder="Enter investment reasoning here...", height=120)
    if st.button("Submit Recommendation", use_container_width=True):
        st.success(f"Tract {st.session_state.active_geoid} recorded.")
    st.markdown('</div>', unsafe_allow_html=True)

# --- RIGHT COLUMN: STATUS & FULL PROFILE ---
with col_right:
    st.subheader("Selection Status")
    st.metric("Tract ID", st.session_state.active_geoid)
    
    # OZ Status
    oz_val = current_tract['OZ_Status']
    oz_class = "status-eligible" if oz_val == "Eligible" else "status-ineligible"
    st.markdown(f"**OZ 2.0 Status**")
    st.markdown(f'<div class="status-box {oz_class}">{oz_val.upper()}</div>', unsafe_allow_html=True)

    st.divider()

    # RESTORED: Full List of Economic Profile Variables
    st.subheader("Economic Profile")
    profile_data = {
        "Indicator": [
            "Total Population", 
            "Median HH Income", 
            "Poverty Rate (%)", 
            "Unemployment Rate (%)", 
            "Student Population (%)", 
            "HS Educated (%)", 
            "College Educated (%)"
        ],
        "Value": [
            f"{current_tract['Total Population']:,.0f}", 
            f"${current_tract['Median Household Income']:,.0f}", 
            f"{current_tract['Poverty Rate']}%", 
            f"{current_tract['Unemployment Rate']}%", 
            f"{current_tract['Student Population']}%", 
            f"{current_tract['High School Educated']}%", 
            f"{current_tract['College Educated']}%"
        ]
    }
    st.table(pd.DataFrame(profile_data))

    # RESTORED: NMTC Metric Below Economic Profile
    nmtc_val = current_tract['NMTC_Status']
    nmtc_class = "status-deep-distress" if nmtc_val == "Deeply Distressed" else ("status-eligible" if nmtc_val == "Eligible" else "status-ineligible")
    st.markdown(f"**NMTC Eligibility**")
    st.markdown(f'<div class="status-box {nmtc_class}">{nmtc_val.upper()}</div>', unsafe_allow_html=True)