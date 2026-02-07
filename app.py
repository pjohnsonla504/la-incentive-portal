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
    st.error(f"Config Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

def get_distance(lat1, lon1, lat2, lon2):
    r = 3958.8 
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master Data
    m = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    
    # Clean Column Names (Crucial to prevent KeyErrors)
    m.columns = m.columns.str.strip()
    
    # Identify GEOID (Column B / Index 1)
    geoid_col = m.columns[1]
    m['GEOID_KEY'] = m[geoid_col].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Dynamic Mapping for Eligibility Columns (In case of typos in CSV)
    def find_col(keywords):
        for col in m.columns:
            if all(k.lower() in col.lower() for k in keywords):
                return col
        return None

    col_p = find_col(['5-Year', 'ACS', 'Eligiblity']) # Eligibility Pool
    col_q = find_col(['Insiders', 'Eligibilty'])      # Current Recommendations
    
    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Anchor Assets
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip().str.lower()
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
        
    return m, g, a, col_p, col_q

master_df, la_geojson, anchor_df, ELIG_COL, REC_COL = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in, p_in = st.text_input("Username").strip(), st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = db.columns.str.strip()
                match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True, "username": u_in, 
                        "role": str(match.iloc[0]['Role']), 
                        "a_type": str(match.iloc[0]['Assigned_Type']), 
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
    st.stop()

# --- 4. REGIONAL BUDGET LOGIC ---
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Calculate budget based on the detected Eligibility column
if ELIG_COL:
    eligible_mask = u_df[ELIG_COL].astype(str).str.lower().str.contains('yes|eligible', na=False)
    total_eligible_in_region = len(u_df[eligible_mask])
    q_limit = max(1, int(total_eligible_in_region * 0.25))
else:
    st.error("Could not find Eligibility column in CSV."); st.stop()

# Tracker: Reading from Sheet1 for "Tracts Recommended"
try:
    existing_recs = conn.read(worksheet="Sheet1", ttl=0)
    user_recs_count = len(existing_recs[existing_recs['User'] == st.session_state["username"]])
except:
    user_recs_count = 0
    existing_recs = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification"])

# --- 5. HEADER & PROGRESS ---
st.title(f"📍 OZ 2.0 Strategy: {st.session_state['a_val']}")
c_bar, c_met = st.columns([0.7, 0.3])
with c_bar:
    st.progress(min(1.0, user_recs_count / q_limit), text=f"Budget Used: {user_recs_count} / {q_limit}")
with c_met:
    st.metric("Tracts Recommended", f"{user_recs_count}")

st.divider()

# --- 6. MAIN INTERFACE ---
col_map, col_profile = st.columns([0.66, 0.33])

with col_map:
    u_df['map_status'] = np.where(eligible_mask, "Eligible", "Ineligible")
    fig = px.choropleth_mapbox(
        u_df, geojson=la_geojson, locations="GEOID_KEY", featureidkey="properties.GEOID_MATCH",
        color="map_status", 
        color_discrete_map={"Eligible": "#28a745", "Ineligible": "#D3D3D3"},
        mapbox_style="carto-positron", zoom=7, center={"lat": 30.5, "lon": -91.5},
        opacity=0.6, hover_data=["GEOID_KEY", "Parish", "Region"]
    )
    fig.update_layout(height=800, margin={"r":0,"t":0,"l":0,"b":0}, legend=dict(orientation="h", y=1.02))
    
    sel_pts = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if sel_pts and sel_pts.get("selection") and sel_pts["selection"].get("points"):
        st.session_state["selected_tract"] = sel_pts["selection"]["points"][0].get("location")

with col_profile:
    st.subheader("Tract Profile")
    sid = st.session_state["selected_tract"]
    
    if sid:
        res = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        st.markdown(f"#### Tract ID: `{sid}`")
        st.write(f"**Parish:** {res.get('Parish', 'N/A')} | **Region:** {res.get('Region', 'N/A')}")
        
        st.markdown("##### 📊 Demographic Snapshot")
        r1 = st.columns(2)
        r1[0].metric("Total Population", f"{res.get('Total Population', 0):,}")
        r1[1].metric("Median Home Value", f"${res.get('Median Home Value', 0):,}")
        
        r2 = st.columns(2)
        r2[0].metric("% Medicaid/Public", f"{res.get('% Medicaid/Public Insurance', '0%')}")
        r2[1].metric("Median Family Income", f"${res.get('Median Family Income', 0):,}")
        
        r3 = st.columns(2)
        r3[0].metric("Poverty Rate (%)", f"{res.get('Poverty Rate (%)', '0%')}")
        r3[1].metric("Labor Force Part. (%)", f"{res.get('Labor Force Participation (%)', '0%')}")
        
        r4 = st.columns(2)
        r4[0].metric("Unemployment Rate (%)", f"{res.get('Unemployment Rate (%)', '0%')}")
        r4[1].metric("HS Degree+", f"{res.get('HS Degree or More (%)', '0%')}")
        
        r5 = st.columns(2)
        # Using .get() with the exact column string to be safe
        r5[0].metric("Bachelor's Degree+", res.get("Bachelor's Degree or More (%)", "0%"))
        r5[1].metric("Broadband Internet", res.get("Broadband Internet (%)", "0%"))
        
        st.metric("Disability Population", res.get("Disability Population (%)", "0%"))
        
        st.divider()
        st.markdown("##### ✍️ Recommendation Justification")
        j_cat = st.selectbox("Category", ["Economic Growth", "Infrastructure", "Housing", "Workforce", "Other"])
        j_text = st.text_area("Justification", key="just_text")
        
        if st.button("Submit Recommendation", type="primary"):
            new_row = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": sid, "Category": j_cat, "Justification": j_text}])
            try:
                conn.update(worksheet="Sheet1", data=pd.concat([existing_recs, new_row], ignore_index=True))
                st.success("Saved!"); st.rerun()
            except Exception as e: st.error(f"Save Failed: {e}")

        st.divider()
        st.markdown("##### ⚓ 5 Nearest Anchor Assets")
        if not anchor_df.empty:
            anchor_df['dist'] = anchor_df.apply(lambda x: get_distance(res['lat'], res['lon'], x['lat'], x['lon']), axis=1)
            st.table(anchor_df.sort_values('dist').head(5)[['name', 'type', 'dist']].rename(columns={'dist': 'Miles'}))
    else:
        st.info("Select a tract on the map.")

# --- 7. SUMMARY TABLE ---
st.divider()
st.subheader("📋 Your Recommendations Summary")
user_recs = existing_recs[existing_recs['User'] == st.session_state["username"]]
if not user_recs.empty:
    st.dataframe(user_recs, use_container_width=True)