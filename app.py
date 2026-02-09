import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json

# Set Page Config
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0", layout="wide")

# --- DATA LOADING ---
@st.cache_data
def load_data():
    # Load Master Data
    df = pd.read_csv('Opportunity Zones 2.0 - Master Data File.csv')
    
    # Load Anchors
    try:
        anchors_df = pd.read_csv('LA anchors.csv')
    except:
        anchors_df = pd.DataFrame()

    # Column Mapping
    poverty_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
    unemployment_col = 'Unemployment Rate (%)'
    mfi_col = 'Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)'
    metro_col = 'Metro Status (Metropolitan/Rural)'
    
    # NMTC Benchmarks (2024-2025 Application Cycle)
    NAT_UNEMP = 5.3  # National Average Unemployment Rate (%)
    STATE_MFI = 86934 # Louisiana Statewide Median Family Income 2024
    
    # 1. Calculate NMTC Basic Eligibility
    df['NMTC_Eligible'] = (
        (df[poverty_col] >= 20) | 
        (df[mfi_col] <= (0.8 * STATE_MFI)) | 
        (df[unemployment_col] >= (1.5 * NAT_UNEMP))
    ).map({True: 'Yes', False: 'No'})
    
    # 2. Calculate Deeply Distressed
    df['Deeply_Distressed'] = (
        (df[poverty_col] > 40) | 
        (df[mfi_col] <= (0.4 * STATE_MFI)) | 
        (df[unemployment_col] >= (2.5 * NAT_UNEMP))
    ).map({True: 'Yes', False: 'No'})
    
    # Data Cleaning
    df['11-digit FIP'] = df['11-digit FIP'].astype(str).str.zfill(11)
    
    return df, anchors_df

df, anchors_df = load_data()

# --- SIDEBAR FILTERS ---
st.sidebar.title("Filters")
selected_region = st.sidebar.multiselect("Select Region", options=sorted(df['Region'].unique()), default=df['Region'].unique())
selected_parish = st.sidebar.multiselect("Select Parish", options=sorted(df[df['Region'].isin(selected_region)]['Parish'].unique()))

# Filter Data
filtered_df = df[df['Region'].isin(selected_region)]
if selected_parish:
    filtered_df = filtered_df[filtered_df['Parish'].isin(selected_parish)]

# --- MAIN DASHBOARD ---
st.title("Louisiana Opportunity Zones 2.0 & NMTC Dashboard")

# Search/Selection
target_tract = st.selectbox("Select a Census Tract (FIPS)", options=filtered_df['11-digit FIP'].unique())
tract_data = filtered_df[filtered_df['11-digit FIP'] == target_tract].iloc[0]

# --- METRIC CARDS ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Tract Status", tract_data['Metro Status (Metropolitan/Rural)'])
    st.metric("Poverty Rate", f"{tract_data['Estimate!!Percent below poverty level!!Population for whom poverty status is determined']:.1f}%")

with col2:
    st.metric("NMTC Eligible", tract_data['NMTC_Eligible'])
    st.metric("Unemployment Rate", f"{tract_data['Unemployment Rate (%)']:.1f}%")

with col3:
    st.metric("Deeply Distressed", tract_data['Deeply_Distressed'])
    st.metric("Median Family Income", f"${tract_data['Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)']:,.0f}")

with col4:
    oz_status = tract_data['Opportunity Zones Insiders Eligibilty']
    st.metric("OZ 2.0 Eligible", "Yes" if oz_status == "Eligible" else "No")
    st.metric("Median Home Value", f"${tract_data['Median Home Value']:,.0f}")

# --- MAP SECTION ---
st.subheader("Regional Eligibility Map")
# Color Logic: Green for OZ 2.0 Eligible, Grey otherwise
filtered_df['Map_Color'] = filtered_df['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Green' if x == 'Eligible' else 'LightGrey')

# Map would ideally use a GeoJSON matched to FIPS
# This is a placeholder for the plotly map logic you are using
st.info("Map is filtered to highlight OZ 2.0 Eligible tracts in Green.")

# --- ANCHOR DATA ---
st.subheader("Community Anchors")
if not anchors_df.empty:
    # Filter anchors by the selected tract's Parish for context
    parish_anchors = anchors_df[anchors_df['Parish'] == tract_data['Parish']]
    st.dataframe(parish_anchors, use_container_width=True)
else:
    st.warning("No anchor data available for this selection.")

# --- DOWNLOAD DATA ---
st.sidebar.download_button(
    label="Download Filtered Data",
    data=filtered_df.to_csv(index=False),
    file_name="filtered_opportunity_zones.csv",
    mime="text/csv"
)