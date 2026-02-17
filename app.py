import streamlit as st
import pandas as pd
import plotly.express as px
import json

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
    # Placeholder for your specific file loading logic
    # Metrics: Opportunity Zones Master File
    # Anchors: LA anchors CSV
    metrics_df = pd.read_csv("opportunity_zones_master.csv")
    anchors_df = pd.read_csv("la_anchors.csv")
    
    with open("louisiana_tracts.json", "r") as f:
        geojson = json.load(f)
    return metrics_df, anchors_df, geojson

metrics_df, anchors_df, la_geojson = load_data()

# --- SIDEBAR / FILTERS ---
st.sidebar.header("Map Filters")
view_level = st.sidebar.selectbox("Select View Level", ["Statewide", "Region", "Parish", "Census Tract"])

# Logic to determine center and zoom based on selection
current_center = LA_CENTER
current_zoom = ZOOM_LEVELS[view_level]

# Filter for OZ 2.0 Eligibility (Tracks highlighted green)
eligible_only = st.sidebar.checkbox("Show Only OZ 2.0 Eligible Tracts", value=True)
if eligible_only:
    # Assuming 'eligibility_status' is the column name from your master file
    display_df = metrics_df[metrics_df['eligibility_status'] == 'Eligible']
else:
    display_df = metrics_df

# --- MAIN CONTENT: MAP ---
st.subheader("Opportunity Zone 2.0 Map")

fig = px.choropleth_mapbox(
    display_df,
    geojson=la_geojson,
    locations="GEOID", # Update to match your CSV/GeoJSON key
    featureidkey="properties.GEOID",
    color="eligibility_status",
    color_discrete_map={"Eligible": "#2ecc71", "Ineligible": "#e74c3c"}, # Green for OZ 2.0
    mapbox_style="carto-positron",
    zoom=current_zoom,
    center=current_center,
    opacity=0.6,
    hover_data=["Parish", "Region"]
)

fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
st.plotly_chart(fig, use_container_with_all_width=True)

# --- ANCHOR ASSETS (Fixed Scrollable Container) ---
st.markdown("---")
st.subheader("Anchor Assets in Selected Area")

# Fix: Scrollable HTML container for anchors to prevent rendering errors
anchor_html = """
<div style="height: 300px; overflow-y: auto; border: 1px solid #ddd; padding: 10px; border-radius: 5px; background-color: #f9f9f9;">
    <ul style="list-style-type: none; padding-left: 0;">
"""

for _, row in anchors_df.iterrows():
    anchor_html += f"<li style='margin-bottom: 10px;'><strong>{row['Anchor_Name']}</strong><br><small>{row['Address']}</small></li>"

anchor_html += "</ul></div>"

st.markdown(anchor_html, unsafe_allow_html=True)