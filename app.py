import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")

st.title("📍 LA Tract Recommendation & Analysis Portal")
st.markdown("Use the dashboard below to analyze census tracts and submit justifications for inclusion.")

# 2. Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Load Data Functions
@st.cache_data(ttl=60)
def load_gsheet_data():
    return conn.read(worksheet="Sheet1")

@st.cache_data
def load_map_assets():
    # Ensure this file exists in your GitHub repo
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

# 4. Metric Cards
st.subheader("Portal Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Tracts", len(df))
with col2:
    # Highlighted tracks are only those eligible for OZ 2.0 [cite: 2026-01-22]
    oz_count = len(df[df['OZ_Status'] == "Opportunity Zone 2.0"])
    st.metric("OZ 2.0 Eligible", oz_count)
with col3:
    submissions = len(df[df['Justification'].notna() & (df['Justification'] != "")])
    st.metric("Recommendations Filed", submissions)

# 5. Census Map with Opportunity Zone Eligibility
st.divider()
st.subheader("Census Map & OZ Eligibility")

# Map Isolation Function [cite: 2026-01-22]
filter_oz = st.checkbox("Isolate Opportunity Zone 2.0 Tracks Only")
map_df = df[df['OZ_Status'] == "Opportunity Zone 2.0"] if filter_oz else df

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
    hover_data=["Tract"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig, use_container_width=True)

# 6. Data Table with Custom Highlighting
st.subheader("Target Census Tracts")
st.markdown("Tracks highlighted green are only those eligible for the Opportunity Zone 2.0 [cite: 2026-01-22].")

def highlight_oz(row):
    # Strict green highlighting for OZ 2.0 only [cite: 2026-01-22]
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
    selected_tract = st.selectbox("Select Tract ID", options=df['Tract'].unique())
    proj_cat = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    justification = st.text_area("Justification / Notes")
    
    submit_btn = st.form_submit_button("Submit Recommendation")

    if submit_btn:
        if not justification:
            st.warning("Please enter a justification.")
        else:
            try:
                current_data = conn.read(worksheet="Sheet1", ttl=0)
                
                new_row = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    "Tract": selected_tract,
                    "Category": proj_cat,
                    "Justification": justification,
                    "OZ_Status": df.loc[df['Tract'] == selected_tract, 'OZ_Status'].values[0]
                }])
                
                updated_df = pd.concat([current_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success("✅ Success! Your recommendation has been saved.")
                st.balloons()
            except Exception as e:
                st.error(f"Submission failed: {e}")