import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import re
from streamlit_gsheets import GSheetsConnection

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(page_title="OZ 2.0 Strategic Planner", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"GSheets Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# Haversine Distance for Anchor Assets
def get_distance(lat1, lon1, lat2, lon2):
    r = 3958.8 
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master File
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Standardize GEOID using your provided header
    geoid_header = "Geography11-digit FIPCode"
    if geoid_header in df.columns:
        df['GEOID_KEY'] = df[geoid_header].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    else:
        # Fallback if the header is slightly different
        df['GEOID_KEY'] = df[df.columns[0]].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Map the 11 Metrics to your updated header list
    m_map = {
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "home": "Median Home Value",
        "medicaid": "% Medicaid/Public Insurance", # Note: Verify if this stayed in Master, otherwise defaults to N/A
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)",
        "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)",
        "web": "Broadband Internet (%)",
        "dis": "Disability Population (%)"
    }

    # Load Geography
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        feature['properties']['GEOID_MATCH'] = str(feature['properties'].get('GEOID', ''))[-11:]

    # Anchor Assets
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip().str.lower()
    except: 
        a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
        
    return df, g, a, m_map

master_df, la_geojson, anchor_df, M_MAP = load_data()

# --- 3. AUTHENTICATION ---
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
                else:
                    st.error("Invalid Username or Password.")
    st.stop()

# --- 4. REGIONAL FILTERING & BUDGETING ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Logic: Green (Eligible) or Grey (Ineligible)
elig_col = "5-year ACS Eligiblity"
u_df['map_status'] = np.where(u_df[elig_col].astype(str).str.lower().str.contains('yes|eligible', na=False), "Eligible", "Ineligible")

# 25% Threshold Calculation
regional_eligible = len(u_df[u_df['map_status'] == "Eligible"])
quota = max(1, int(regional_eligible * 0.25))

# Tracker
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
c_bar.progress(min(1.0, user_count/quota), text=f"Tracts Recommended: {user_count} / {quota}")
c_num.metric("My Total Nominations", user_count)

st.divider()

col_map, col_data = st.columns([0.66, 0.33])

with col_map:
    
    fig = px.choropleth_mapbox(
        u_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="map_status", color_discrete_map={"Eligible": "#28a745", "Ineligible": "#737373"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 30.8, "lon": -91.5},
        opacity=0.7, hover_data=["GEOID_KEY", "Parish", "Region"]
    )
    fig.update_layout(height=800, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", y=1.02))
    
    selected = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected and selected.get("selection") and selected["selection"].get("points"):
        st.session_state["selected_tract"] = selected["selection"]["points"][0].get("location")

with col_data:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    
    if sid:
        row = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        st.write(f"**ID:** `{sid}` | **Parish:** {row.get('Parish')} | **Region:** {row.get('Region')}")
        
        st.markdown("##### 📊 Demographics")
        def show(lbl, k):
            h = M_MAP[k]
            val = row.get(h, "N/A")
            # Inline formatting for better readability
            if isinstance(val, (int, float)):
                if "%" in lbl: val = f"{val:.1f}%"
                elif "$" in lbl or "Income" in lbl or "Value" in lbl: val = f"${val:,.0f}"
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
        st.markdown("##### ✍️ Submission & Justification")
        cat = st.selectbox("Category", ["Economic Growth", "Infrastructure", "Housing", "Workforce Development", "Other"])
        note = st.text_area("Written Justification", help="Explain why this tract should be an Opportunity Zone.")
        
        if st.button("Submit Recommendation", type="primary"):
            if user_count >= quota:
                st.error("Budget limit reached for your region.")
            elif not note:
                st.warning("Please provide a justification.")
            else:
                new_row = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": sid, "Category": cat, "Justification": note}])
                try:
                    conn.update(worksheet="Sheet1", data=pd.concat([current_sheet, new_row], ignore_index=True))
                    st.success("Tract Successfully Nominated!"); st.rerun()
                except Exception as e: 
                    st.error(f"Google Sheets Update Error: {e}")

        st.divider()
        st.markdown("##### ⚓ 5 Nearest Anchors")
        if not anchor_df.empty and 'lat' in row:
            anchor_df['dist'] = anchor_df.apply(lambda x: get_distance(row['lat'], row['lon'], x['lat'], x['lon']), axis=1)
            st.table(anchor_df.sort_values('dist').head(5)[['name', 'type', 'dist']].rename(columns={'dist': 'Miles'}))
    else:
        st.info("Select a tract on the map to view data and submit a nomination.")

# --- 6. SUMMARY TABLE ---
st.divider()
st.subheader("📋 My Selected Tracts")
if not user_recs.empty:
    st.dataframe(user_recs[['GEOID', 'Category', 'Justification', 'Date']], use_container_width=True)