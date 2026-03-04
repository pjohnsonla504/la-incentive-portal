import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# --- CONFIGURATION ---
st.set_page_config(page_title="Opportunity Zones 2.0 Explorer", layout="wide")

def load_data():
    # Load Master Data (Map Eligibility & Metrics)
    # This uses the specific Master Data File from your records
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File (V2).csv")
    
    # Clean numeric columns that may have commas or non-numeric placeholder strings
    cols_to_fix = ['Median Household Income', 'Population']
    for col in cols_to_fix:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').replace('-', '0'), errors='coerce')

    # Load Anchors Data
    try:
        anchors_df = pd.read_csv("LA anchors.csv")
    except FileNotFoundError:
        anchors_df = pd.DataFrame() # Fallback if file isn't present
        
    return df, anchors_df

df, anchors_df = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.header("Map Controls")

# OZ 2.0 Eligibility Toggle (Highlighted Green per Instructions)
show_oz2 = st.sidebar.checkbox("Highlight OZ 2.0 Eligible Tracts", value=True)

# OZ 1.0 Overlay Toggle
show_oz1 = st.sidebar.checkbox("Overlay Current OZ 1.0 (Expires 2028)", value=False)

# Anchor Toggle
show_anchors = st.sidebar.checkbox("Show Economic Anchors", value=True)

# Metric Selection for Heatmap (Based on CSV Columns)
metric_options = {
    "Poverty %": "Poverty %",
    "Unemployment %": "Unemploy  %",
    "Median Income": "Median Household Income",
    "Broadband Accessibility": "% of tract with Broadband Accessibility"
}
selected_metric_label = st.sidebar.selectbox("Select Metric Layer", list(metric_options.keys()))
selected_col = metric_options[selected_metric_label]

# --- DATA PROCESSING ---
# Filter for Green Highlight (OZ 2.0 Eligible Only)
oz2_eligible = df[df['Eligibility for OZ 2.0 Designation'] == 'ELIGIBLE'].copy()

# Filter for OZ 1.0 Overlay
oz1_tracts = df[df['Current OZ 1.0 tract (expires Dec. 2028)'] == 'yes'].copy()

# --- MAP GENERATION ---
st.title("Louisiana Opportunity Zones 2.0 Transition Map")

# Base Choropleth for Metrics
fig = px.choropleth_mapbox(
    df,
    geojson=None, # Streamlit/Plotly will look for standard FIPS geometry
    locations="GEOID",
    color=selected_col,
    color_continuous_scale="Viridis",
    mapbox_style="carto-positron",
    zoom=6.5,
    center={"lat": 31.0, "lon": -92.0},
    opacity=0.3,
    hover_data=["Parish", "Region", "Eligibility for OZ 2.0 Designation"],
    labels={selected_col: selected_metric_label}
)

# Add OZ 2.0 Eligibility Layer (Green Highlight)
if show_oz2:
    fig.add_trace(
        go.Choroplethmapbox(
            geojson=None,
            locations=oz2_eligible["GEOID"],
            z=[1] * len(oz2_eligible),
            colorscale=[[0, "rgba(0, 255, 0, 0.4)"], [1, "rgba(0, 255, 0, 0.4)"]],
            showscale=False,
            name="OZ 2.0 Eligible",
            hovertemplate="<b>OZ 2.0 Eligible Tract</b><extra></extra>"
        )
    )

# Add OZ 1.0 Overlay (Outline)
if show_oz1:
    fig.add_trace(
        go.Choroplethmapbox(
            geojson=None,
            locations=oz1_tracts["GEOID"],
            z=[1] * len(oz1_tracts),
            colorscale=[[0, "rgba(255, 165, 0, 0)"], [1, "rgba(255, 165, 0, 0)"]], # Transparent fill
            marker_line_color="orange",
            marker_line_width=2,
            showscale=False,
            name="Current OZ 1.0",
            hovertemplate="<b>Current OZ 1.0 Tract</b><br>Expires 2028<extra></extra>"
        )
    )

# Add Anchors (Scatter Layer)
if show_anchors and not anchors_df.empty:
    fig.add_trace(
        go.Scattermapbox(
            lat=anchors_df["Latitude"],
            lon=anchors_df["Longitude"],
            mode="markers",
            marker=go.scattermapbox.Marker(size=8, color="red"),
            text=anchors_df["Anchor Name"],
            name="Economic Anchors"
        )
    )

fig.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, height=700)
st.plotly_chart(fig, use_container_width=True)

# --- METRIC CARDS ---
st.subheader(f"Tract Statistics: {selected_metric_label}")
col1, col2, col3 = st.columns(3)

avg_val = df[selected_col].mean()
oz2_avg = oz2_eligible[selected_col].mean()

col1.metric("Statewide Average", f"{avg_val:.1f}")
col2.metric("OZ 2.0 Eligible Average", f"{oz2_avg:.1f}")
col3.metric("Tracts Eligible for 2.0", len(oz2_eligible))

st.info("Note: Tracks highlighted green are those eligible for the Opportunity Zone 2.0 expansion.")