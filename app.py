import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")

st.title("📍 LA Tract Recommendation & Analysis Portal")

# 2. Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Load Data Functions
@st.cache_data(ttl=60)
def load_gsheet_data():
    data = conn.read(worksheet="Sheet1")
    # Clean column headers
    data.columns = [str(c).strip() for c in data.columns]
    
    # FORCE FORMATTING: Ensure Tracts are strings and handle leading zeros
    if 'Tract' in data.columns:
        # Remove decimals if they exist (e.g., 2201.0 -> 2201)
        data['Tract'] = data['Tract'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        
        # Census GEOIDs for Louisiana should be 11 digits. 
        # If your sheet stripped the leading '0', this adds it back.
        data['Tract'] = data['Tract'].apply(lambda x: x.zfill(11) if len(x) == 10 else x)
        
    return data

@st.cache_data
def load_map_assets():
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return geojson

# Load Assets
try:
    df = load_gsheet_data()
    la_geojson = load_map_assets()
except Exception as e:
    st.error(f"Error loading assets: {e}")
    st.stop()

# 4. Metric Cards (Restored)
st.subheader("Portal Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Tracts", len(df))
with col2:
    # Logic: Highlighted green are only those eligible for OZ 2.0 [cite: 2026-01-22]
    oz_count = len(df[df['OZ_Status'] == "Opportunity Zone 2.0"])
    st.metric("OZ 2.0 Eligible", oz_count)
with col3:
    submissions = len(df[df['Justification'].notna() & (df['Justification'] != "")])
    st.metric("Recommendations Filed", submissions)

# 5. Map & Isolation Controls (Restored)
st.divider()
st.subheader("Census Map & Selection")

# Isolation Functions
with st.expander("Map Filters & Isolation Controls", expanded=True):
    iso_col1, iso_col2 = st.columns(2)
    with iso_col1:
        # Toggle to isolate OZ 2.0 tracks [cite: 2026-01-22]
        filter_oz = st.toggle("Isolate Opportunity Zone 2.0 Tracks Only", value=False)
    with iso_col2:
        search_tract = st.text_input("Search for specific Tract ID on Map")

# Filter logic for the Map
map_df = df.copy()
if filter_oz:
    map_df = map_df[map_df['OZ_Status'] == "Opportunity Zone 2.0"]
if search_tract:
    map_df = map_df[map_df['Tract'].str.contains(search_tract)]

# Build Map using GEOID
fig = px.choropleth_mapbox(
    map_df,
    geojson=la_geojson,
    locations="Tract",
    featureidkey="properties.GEOID", 
    color="OZ_Status",
    color_discrete_map={"Opportunity Zone 2.0": "#28a745", "Ineligible": "#6c757d"},
    mapbox_style="carto-positron",
    zoom=6,
    center={"lat": 30.9843, "lon": -91.9623},
    opacity=0.6,
    hover_data=["Tract", "OZ_Status"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig, use_container_width=True)

# 6. Data Table with Green Highlighting [cite: 2026-01-22]
st.subheader("Tract Eligibility List")
def highlight_oz(row):
    if str(row.get('OZ_Status', '')).strip() == "Opportunity Zone 2.0":
        return ['background-color: #d4edda'] * len(row)
    return [''] * len(row)

st.dataframe(
    df.style.apply(highlight_oz, axis=1), 
    use_container_width=True, 
    hide_index=True
)

# 7. Recommendation Form
st.divider()
st.subheader("Submit a Recommendation")

with st.form("recommendation_form", clear_on_submit=True):
    # This dropdown allows selection from your sheet's tracts
    tract_options = sorted(df['Tract'].unique())
    selected_tract = st.selectbox("Select Tract ID", options=tract_options)
    
    proj_cat = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    justification = st.text_area("Justification / Notes")
    
    submit_btn = st.form_submit_button("Submit Recommendation")

    if submit_btn:
        if not justification:
            st.warning("Please enter a justification.")
        else:
            try:
                # Refresh data
                current_data = conn.read(worksheet="Sheet1", ttl=0)
                
                # Safety lookup for OZ Status
                match = df.loc[df['Tract'] == selected_tract, 'OZ_Status']
                oz_val = match.values[0] if not match.empty else "N/A"

                new_row = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    "Tract": selected_tract,
                    "Category": proj_cat,
                    "Justification": justification,
                    "OZ_Status": oz_val
                }])
                
                updated_df = pd.concat([current_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success(f"✅ Success! Recommendation for {selected_tract} saved.")
                st.balloons()
                st.cache_data.clear() # Forces a refresh of the table/map
            except Exception as e:
                st.error(f"Submission failed: {e}")