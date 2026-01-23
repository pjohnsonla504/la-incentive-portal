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
def load_master_data():
    # Pulling from your GitHub CSV file
    master_df = pd.read_csv("tract_data_final.csv")
    master_df.columns = [str(c).strip() for c in master_df.columns]
    
    # Ensure GEOID is a clean 11-digit string for the map
    if 'GEOID' in master_df.columns:
        master_df['GEOID'] = master_df['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
        master_df['GEOID'] = master_df['GEOID'].apply(lambda x: x.zfill(11) if len(x) == 10 else x)
    
    return master_df

@st.cache_data(ttl=60)
def load_recommendations():
    try:
        recs = conn.read(worksheet="Sheet1")
        recs.columns = [str(c).strip() for c in recs.columns]
        return recs
    except:
        return pd.DataFrame(columns=["Date", "GEOID", "Category", "Justification", "Is_Eligible"])

@st.cache_data
def load_map_assets():
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return geojson

# Load Assets
try:
    master_df = load_master_data()
    la_geojson = load_map_assets()
    recs_df = load_recommendations()
except Exception as e:
    st.error(f"Error loading system files: {e}")
    st.stop()

# 4. Metric Cards
st.subheader("Portal Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Master Tracts", len(master_df))
with col2:
    # Logic: Highlights only those eligible for Opportunity Zone 2.0 [cite: 2026-01-22]
    # We use 'Is_Eligible' based on your CSV headers
    eligible_count = len(master_df[master_df['Is_Eligible'] == 1])
    st.metric("Eligible Tracts", eligible_count)
with col3:
    st.metric("Recommendations Saved", len(recs_df))

# 5. Map & Isolation Controls (Restored)
st.divider()
st.subheader("Census Map & Selection")

# Sidebar/Top controls for Isolation
with st.expander("Map Filters & Regional Isolation", expanded=True):
    iso_col1, iso_col2 = st.columns(2)
    with iso_col1:
        # User requested: Isolate by REDO region [cite: 2026-01-22]
        regions = ["All"] + sorted(master_df['REDO_Region'].dropna().unique().tolist())
        selected_region = st.selectbox("Isolate by REDO Region", options=regions)
    with iso_col2:
        # Toggle for Eligibility
        only_eligible = st.toggle("Show Only Eligible Tracts", value=False)

# Apply filters to Map Data
map_plot_df = master_df.copy()
if selected_region != "All":
    map_plot_df = map_plot_df[map_plot_df['REDO_Region'] == selected_region]
if only_eligible:
    map_plot_df = map_plot_df[map_plot_df['Is_Eligible'] == 1]

# Build Map
fig = px.choropleth_mapbox(
    map_plot_df,
    geojson=la_geojson,
    locations="GEOID",
    featureidkey="properties.GEOID", 
    color="Is_Eligible",
    # 1 (Eligible) = Green, 0 (Ineligible) = Gray [cite: 2026-01-22]
    color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
    mapbox_style="carto-positron",
    zoom=6,
    center={"lat": 30.9843, "lon": -91.9623},
    opacity=0.6,
    hover_data=["GEOID", "Parish", "REDO_Region"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
st.plotly_chart(fig, use_container_width=True)

# 6. Recommendation Form (Writes to Google Sheets)
st.divider()
st.subheader("Submit a Recommendation")

with st.form("recommendation_form", clear_on_submit=True):
    # Selection pulled from CSV GEOID column
    selected_geoid = st.selectbox("Select GEOID", options=sorted(master_df['GEOID'].unique()))
    proj_cat = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    justification = st.text_area("Justification / Notes")
    
    submit_btn = st.form_submit_button("Submit to Google Sheets")

    if submit_btn:
        if not justification:
            st.warning("Please enter a justification.")
        else:
            try:
                # Capture eligibility for the Google Sheet record
                match = master_df.loc[master_df['GEOID'] == selected_geoid, 'Is_Eligible']
                elig_val = "Eligible" if not match.empty and match.values[0] == 1 else "Ineligible"

                new_row = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    "GEOID": selected_geoid,
                    "Category": proj_cat,
                    "Justification": justification,
                    "Is_Eligible": elig_val
                }])
                
                # Append to Google Sheet
                current_sheet_data = conn.read(worksheet="Sheet1", ttl=0)
                updated_df = pd.concat([current_sheet_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success(f"✅ Success! Recommendation for {selected_geoid} saved.")
                st.balloons()
            except Exception as e:
                st.error(f"Submission failed: {e}")

# 7. Recent Submissions View
if not recs_df.empty:
    st.subheader("Recent Activity (from Google Sheets)")
    st.dataframe(recs_df.tail(10), use_container_width=True, hide_index=True)