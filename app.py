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

# Haversine Distance Formula for Anchor Assets
def get_distance(lat1, lon1, lat2, lon2):
    r = 3958.8 
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- 2. DATA LOADING & PROCESSING ---
@st.cache_data(ttl=60)
def load_data():
    csv_filename = "Opportunity Zones 2.0 - Master Data File.csv"
    m = pd.read_csv(csv_filename)
    
    # Identify GEOID (Column B / Index 1)
    geoid_col = m.columns[1]
    m['GEOID_KEY'] = m[geoid_col].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Clean column names
    m.columns = m.columns.str.strip()
    
    # Load Boundaries
    with open("tl_2025_22_tract.json") as f: 
        g = json.load(f)
    for feature in g['features']:
        raw_id = str(feature['properties'].get('GEOID', ''))
        feature['properties']['GEOID_MATCH'] = "".join(re.findall(r'\d+', raw_id))[-11:]

    # Anchor Assets
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = [c.strip().lower() for c in a.columns]
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
        
    return m, g, a

master_df, la_geojson, anchor_df = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in, p_in = st.text_input("Username").strip(), st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = [c.strip() for c in db.columns]
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

# --- 4. REGIONAL FILTERING & COUNTERS ---
# Filter to the user's region
u_df = master_df.copy()
if st.session_state["role"].lower() != "admin" and st.session_state["a_val"].lower() != "all":
    u_df = u_df[u_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Count Eligibility
# Based on Column P (5-Year ACS Eligibility)
eligible_tracts = u_df[u_df['5-Year ACS Eligiblity'].astype(str).str.lower().str.contains('yes|eligible', na=False)]
q_limit = max(1, int(len(eligible_tracts) * 0.25))

# Count Current User Recommendations (Column Q)
# In a real app, this would read from the GSheet; here it checks the Column Q status in the filtered df
user_recs = len(u_df[u_df['Opportunity Zones Insiders Eligibilty'].astype(str).str.lower().str.contains('yes|eligible', na=False)])

# --- 5. TOP SECTION: PROGRESS ---
st.title(f"📍 OZ 2.0 Strategy: {st.session_state['a_val']}")
st.markdown("### Recommendation Counter")
c_bar, c_met = st.columns([0.8, 0.2])
with c_bar:
    st.progress(min(1.0, user_recs / q_limit), text=f"{user_recs} of {q_limit} Allocated Recommendation Budget")
with c_met:
    st.metric("Tracts Recommended", f"{user_recs}")

st.divider()

# --- 6. MAIN INTERFACE (2/3 MAP, 1/3 PROFILE) ---
col_map, col_profile = st.columns([0.66, 0.33])

with col_map:
    # Logic: Only Green (Eligible) or Grey (Ineligible)
    u_df['map_status'] = np.where(u_df['5-Year ACS Eligiblity'].astype(str).str.lower().str.contains('yes|eligible', na=False), "Eligible", "Ineligible")
    
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
        
        # Identification
        st.markdown(f"#### Tract ID: `{sid}`")
        st.write(f"**Parish:** {res.get('Parish', 'N/A')}")
        st.write(f"**Region:** {res.get('Region', 'N/A')}")
        
        # Demographic Snapshot
        st.markdown("##### 📊 Demographic Snapshot")
        m1, m2 = st.columns(2)
        m1.metric("Total Population", f"{res.get('Total Population', 0):,}")
        m2.metric("Median Home Value", f"${res.get('Median Home Value', 0):,}")
        
        m3, m4 = st.columns(2)
        m3.metric("Public Insurance", f"{res.get('% Medicaid/Public Insurance', '0%')}")
        m4.metric("Median Family Income", f"${res.get('Median Family Income', 0):,}")
        
        m5, m6 = st.columns(2)
        m5.metric("Poverty Rate", f"{res.get('Poverty Rate (%)', '0%')}")
        m6.metric("Labor Participation", f"{res.get('Labor Force Participation (%)', '0%')}")
        
        m7, m8 = st.columns(2)
        m7.metric("Unemployment Rate", f"{res.get('Unemployment Rate (%)', '0%')}")
        m8.metric("HS Degree+", f"{res.get('HS Degree or More (%)', '0%')}")
        
        m9, m10 = st.columns(2)
        m9.metric("Bachelor's Degree+", f"{res.get(\"Bachelor's Degree or More (%)\", '0%')}")
        m10.metric("Broadband Access", f"{res.get('Broadband Internet (%)', '0%')}")
        
        st.metric("Disability Population", f"{res.get('Disability Population (%)', '0%')}")
        
        # Justification Area
        st.divider()
        st.markdown("##### ✍️ Recommendation Justification")
        j_cat = st.selectbox("Justification Category", ["Economic Growth", "Infrastructure", "Housing", "Workforce Development", "Other"])
        j_text = st.text_area("Written Justification", placeholder="Describe why this tract should be nominated...")
        if st.button("Submit Recommendation"):
            st.success(f"Tract {sid} submitted for {j_cat}!")

        # Nearest Anchors (Top 5)
        st.divider()
        st.markdown("##### ⚓ Nearest Anchor Assets")
        if not anchor_df.empty and 'lat' in res:
            anchor_df['dist'] = anchor_df.apply(lambda x: get_distance(res['lat'], res['lon'], x['lat'], x['lon']), axis=1)
            st.table(anchor_df.sort_values('dist').head(5)[['name', 'type', 'dist']].rename(columns={'dist': 'Miles'}))
    else:
        st.info("Select a tract on the map to view demographics and anchors.")

# --- 7. FOOTER: SUMMARY TABLE ---
st.divider()
st.subheader("📋 Your Current Recommendations")
# Show the tracts that are already marked in Column Q
rec_table = u_df[u_df['Opportunity Zones Insiders Eligibilty'].astype(str).str.lower().str.contains('yes|eligible', na=False)]
if not rec_table.empty:
    st.dataframe(rec_table[['GEOID_KEY', 'Parish', 'Region', 'Poverty Rate (%)', 'Median Family Income']], use_container_width=True)
else:
    st.write("No recommendations selected yet.")