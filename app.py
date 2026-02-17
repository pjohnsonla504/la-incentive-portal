import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os

# --- CONFIGURATION ---
st.set_page_config(layout="wide", page_title="Louisiana Opportunity Zones 2.0")

# Default Louisiana Map View (Statewide)
LA_CENTER = {"lat": 30.9843, "lon": -91.9623}
LA_DEFAULT_ZOOM = 6.2

# Dynamic Zoom Levels based on selection type
ZOOM_LEVELS = {
    "Statewide": 6.2,
    "Region": 7.5,
    "Parish": 9.0,
    "Census Tract": 12.0
}

# --- DATA LOADING ---
@st.cache_data
def load_data():
    base_path = os.path.dirname(__file__)
    
    # Updated to your exact filename
    # Note: Ensure this file is in the same folder as app.py in GitHub
    master_file_name = "Opportunity Zones 2.0 - Master Data File.csv"
    metrics_path = os.path.join(base_path, master_file_name)
    anchors_path = os.path.join(base_path, "la_anchors.csv")
    geojson_path = os.path.join(base_path, "louisiana_tracts.json")

    # Debugging check if file is missing
    if not os.path.exists(metrics_path):
        available_files = os.listdir(base_path)
        st.error(f"Cannot find: {master_file_name}")
        st.info(f"Files found in directory: {available_files}")
        st.stop()

    # Loading the data
    metrics_df = pd.read_csv(metrics_path)
    anchors_df = pd.read_csv(anchors_path)
    
    with open(geojson_path, "r") as f:
        geojson = json.load(f)
        
    return metrics_df, anchors_df, geojson

# Initialize Data
metrics_df, anchors_df, la_geojson = load_data()

# --- SIDEBAR / FILTERS ---
st.sidebar.header("Map Filters")
view_level = st.sidebar.selectbox("Select View Level", ["Statewide", "Region", "Parish", "Census Tract"])

# Map View Logic
current_center = LA_CENTER
current_zoom = ZOOM_LEVELS[view_level]

# Filter for OZ 2.0 Eligibility (Tracks highlighted green)
eligible_only = st.sidebar.checkbox("Show Only OZ 2.0 Eligible Tracts", value=True)
if eligible_only:
    # Ensure 'eligibility_status' matches the column name in your CSV
    display_df = metrics_df[metrics_df['eligibility_status'] == 'Eligible']
else:
    display_df = metrics_df

# --- MAIN CONTENT: MAP ---
st.subheader("Opportunity Zone 2.0 Map")

fig = px.choropleth_mapbox(
    display_df,
    geojson=la_geojson,
    locations="GEOID", 
    featureidkey="properties.GEOID",
    color="eligibility_status",
    color_discrete_map={"Eligible": "#2ecc71", "Ineligible": "#e74c3c"},
    mapbox_style="carto-positron",
    zoom=current_zoom,
    center=current_center,
    opacity=0.6,
    hover_data=["Parish", "Region"]
)

fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
st.plotly_chart(fig, use_container_with_all_width=True)

# --- ANCHOR ASSETS (Fixed Scrollable Logic) ---
st.markdown("---")
st.subheader("Anchor Assets in Selected Area")

# Scrollable container for assets
anchor_html = """
<div style="height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 15px; border-radius: 8px; background-color: #ffffff; color: #333; font-family: sans-serif;">
    <ul style="list-style-type: none; padding-left: 0;">
"""

for _, row in anchors_df.iterrows():
    name = row.get('Anchor_Name', 'Unknown Asset')
    addr = row.get('Address', 'Address not listed')
    anchor_html += f"""
    <li style='margin-bottom: 12px; border-bottom: 1px solid #f0f0f0; padding-bottom: 8px;'>
        <span style='color: #2c3e50; font-size: 1.1em;'><strong>{name}</strong></span><br>
        <span style='color: #7f8c8d; font-size: 0.9em;'>{addr}</span>
    </li>
    """

anchor_html += "</ul></div>"

st.markdown(anchor_html, unsafe_allow_html=True)