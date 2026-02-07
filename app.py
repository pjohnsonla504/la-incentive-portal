import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="OZ 2.0 Strategic Planner", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"GSheets Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Standardize GEOID
    geoid_header = "Geography11-digit FIPCode"
    if geoid_header not in df.columns:
        geoid_header = df.columns[1]
    df['GEOID_KEY'] = df[geoid_header].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Exact Header Mapping
    m_map = {
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "home": "Median Home Value",
        "medicaid": "% Medicaid/Public Insurance",
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)",
        "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)",
        "web": "Broadband Internet (%)",
        "dis": "Disability Population (%)"
    }

    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = raw_id.split('.')[0][-11:].zfill(11)

    return df, g, m_map

master_df, la_geojson, M_MAP = load_data()

# --- 3. AUTHENTICATION (Standard Login Logic) ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Access")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login"):
            u, p = st.text_input("User").strip(), st.text_input("Pass", type="password").strip()
            if st.form_submit_button("Login"):
                user_db = conn.read(worksheet="Users", ttl=0)
                user_db.columns = user_db.columns.str.strip()
                match = user_db[(user_db['Username'].astype(str) == u) & (user_db['Password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True, "username": u, 
                        "role": str(match.iloc[0]['Role']), 
                        "a_type": str(match.iloc[0]['Assigned_Type']), 
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# --- 4. REGIONAL FILTERING & NO-COLOR LOGIC ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Define Eligibility: Only 'Eligible' gets a visible color
elig_col = "5-year ACS Eligiblity"
u_df['map_status'] = np.where(
    u_df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 
    "Eligible", 
    "Ineligible"
)

# Quota Logic
regional_eligible = len(u_df[u_df['map_status'] == "Eligible"])
quota = max(1, int(regional_eligible * 0.25))

try:
    current_sheet = conn.read(worksheet="Sheet1", ttl=0)
    user_recs = current_sheet[current_sheet['User'] == st.session_state["username"]]
    user_count = len(user_recs)
except:
    user_count = 0
    current_sheet = pd.DataFrame()

# --- 5. INTERFACE ---
st.title(f"📍 OZ 2.0 Strategic Planner: {st.session_state['a_val']}")
c_bar, c_num = st.columns([0.7, 0.3])
c_bar.progress(min(1.0, user_count/quota), text=f"Nominations: {user_count} / {quota}")
c_num.metric("My Total Nominations", user_count)

st.divider()

col_map, col_data = st.columns([0.66, 0.33])

with col_map:
    # Set Ineligible to transparent/no color
    fig = px.choropleth_mapbox(
        u_df, 
        geojson=la_geojson, 
        locations="GEOID_KEY", 
        featureidkey="properties.GEOID_MATCH",
        color="map_status", 
        color_discrete_map={
            "Eligible": "#28a745",        # Solid Green
            "Ineligible": "rgba(0,0,0,0)" # Transparent (No Color)
        },
        category_orders={"map_status": ["Eligible", "Ineligible"]},
        mapbox_style="carto-positron", 
        zoom=7, 
        center={"lat": 30.8, "lon": -91.5},
        opacity=0.8, 
        hover_data=["GEOID_KEY", "Parish"]
    )
    
    # Force thin borders for the "no color" tracts so they are still selectable
    fig.update_traces(marker_line_width=0.5, marker_line_color="lightgrey")
    
    fig.update_layout(
        height=800, 
        margin={"r":0,"t":0,"l":0,"b":0},
        legend=dict(title="OZ 2.0 Eligibility", orientation="h", y=1.02, x=0)
    )
    
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected and selected.get("selection") and selected["selection"].get("points"):
        raw_sel = str(selected["selection"]["points"][0].get("location"))
        st.session_state["selected_tract"] = raw_sel.split('.')[0].zfill(11)

with col_data:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    matching_rows = master_df[master_df['GEOID_KEY'] == sid]
    
    if sid and not matching_rows.empty:
        row = matching_rows.iloc[0]
        st.write(f"**ID:** `{sid}` | **Parish:** {row.get('Parish')}")
        
        # Demographic Metrics
        st.divider()
        def show(lbl, k):
            h = M_MAP.get(k)
            val = row.get(h, "N/A")
            st.metric(lbl, val)

        m1, m2 = st.columns(2)
        with m1:
            show("Population", "pop")
            show("Poverty %", "poverty")
            show("Unemployment", "unemp")
            show("Bachelor's+", "bach")
            show("Disability %", "dis")
        with m2:
            show("Median Home", "home")
            show("Median Income", "income")
            show("Labor Part. %", "labor")
            show("HS Degree+", "hs")
            show("Broadband %", "web")

        st.divider()
        st.markdown("##### ✍️ Submission")
        cat = st.selectbox("Category", ["Economic Growth", "Infrastructure", "Housing", "Workforce Development", "Other"])
        note = st.text_area("Justification")
        
        if st.button("Submit Recommendation", type="primary"):
            if user_count >= quota:
                st.error("Limit reached.")
            elif not note:
                st.warning("Please add a justification.")
            else:
                new_row = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": sid, "Category": cat, "Justification": note}])
                try:
                    conn.update(worksheet="Sheet1", data=pd.concat([current_sheet, new_row], ignore_index=True))
                    st.success("Submitted!"); st.rerun()
                except Exception as e: st.error(f"Error: {e}")
    else:
        st.info("Select a highlighted tract on the map to begin.")

# --- 6. SUMMARY ---
st.divider()
st.subheader("📋 My Selected Tracts")
if not user_recs.empty:
    st.dataframe(user_recs[['GEOID', 'Category', 'Justification', 'Date']], use_container_width=True)