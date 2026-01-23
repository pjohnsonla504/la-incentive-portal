import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")

st.title("📍 LA Tract Recommendation & Analysis Portal")

# 2. Establish Google Sheets Connection (For Recommendations Only)
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Load Data Functions
@st.cache_data(ttl=60)
def load_master_data():
    # Pulling from your GitHub CSV file
    master_df = pd.read_csv("tract_data_final.csv")
    master_df['Tract'] = master_df['Tract'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    master_df['Tract'] = master_df['Tract'].apply(lambda x: x.zfill(11) if len(x) == 10 else x)
    return master_df

@st.cache_data(ttl=60)
def load_recommendations():
    # Pulling from Google Sheets
    try:
        recs = conn.read(worksheet="Sheet1")
        recs.columns = [str(c).strip() for c in recs.columns]
        return recs
    except:
        return pd.DataFrame(columns=["Date", "Tract", "Category", "Justification", "OZ_Status"])

@st.cache_data
def load_map_assets():
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return geojson

# Load All Assets
try:
    master_df = load_master_data()
    la_geojson = load_map_assets()
    recs_df = load_recommendations()
except Exception as e:
    st.error(f"Error loading files: {e}")
    st.stop()

# 4. Metric Cards
st.subheader("Portal Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Tracts (CSV)", len(master_df))
with col2:
    # Logic: Green highlight for OZ 2.0 [cite: 2026-01-22]
    oz_count = len(master_df[master_df['OZ_Status'] == "Opportunity Zone 2.0"])
    st.metric("OZ 2.0 Eligible", oz_count)
with col3:
    st.metric("Total Recommendations", len(recs_df))

# 5. Map & Isolation Controls
st.divider()
st.subheader("Census Map & Selection")

filter_oz = st.toggle("Isolate Opportunity Zone 2.0 Tracks Only", value=False)

# Map is informed by the CSV and JSON
map_plot_df = master_df.copy()
if filter_oz:
    map_plot_df = map_plot_df[map_plot_df['OZ_Status'] == "Opportunity Zone 2.0"]

fig = px.choropleth_mapbox(
    map_plot_df,
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

# 6. Recommendation Form (Updates Google Sheet)
st.divider()
st.subheader("Submit a Recommendation")

with st.form("recommendation_form", clear_on_submit=True):
    # Dropdown pulls from the CSV master list
    selected_tract = st.selectbox("Select Tract ID from Master List", options=sorted(master_df['Tract'].unique()))
    proj_cat = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    justification = st.text_area("Justification / Notes")
    
    submit_btn = st.form_submit_button("Submit to Google Sheets")

    if submit_btn:
        if not justification:
            st.warning("Please enter a justification.")
        else:
            try:
                # Find OZ status from CSV to save to Sheet
                match = master_df.loc[master_df['Tract'] == selected_tract, 'OZ_Status']
                oz_val = match.values[0] if not match.empty else "N/A"

                # Prepare the row for Google Sheets
                new_row = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    "Tract": selected_tract,
                    "Category": proj_cat,
                    "Justification": justification,
                    "OZ_Status": oz_val
                }])
                
                # Append to Google Sheet
                current_sheet_data = conn.read(worksheet="Sheet1", ttl=0)
                updated_df = pd.concat([current_sheet_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success(f"✅ Recommendation for {selected_tract} saved to Google Sheets!")
                st.balloons()
            except Exception as e:
                st.error(f"Submission failed: {e}")

# 7. Display Current Recommendations (Optional - pulled from Sheet)
if not recs_df.empty:
    st.subheader("Existing Recommendations (from Google Sheets)")
    st.dataframe(recs_df, use_container_width=True, hide_index=True)