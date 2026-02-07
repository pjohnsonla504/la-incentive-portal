import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")

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

# --- AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login"):
        u_in, p_in = st.text_input("User").strip(), st.text_input("Pass", type="password").strip()
        if st.form_submit_button("Access"):
            db = conn.read(worksheet="Users", ttl=0)
            db.columns = [c.strip() for c in db.columns]
            match = db[(db['Username'].astype(str)==u_in) & (db['Password'].astype(str)==p_in)]
            if not match.empty:
                st.session_state.update({
                    "authenticated": True, 
                    "username": u_in, 
                    "role": str(match.iloc[0]['Role']), 
                    "a_type": str(match.iloc[0]['Assigned_Type']), 
                    "a_val": str(match.iloc[0]['Assigned_Value'])
                })
                st.rerun()
    st.stop()

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    def clean_geoid(s):
        import re
        s = str(s).strip()
        match = re.search(r'(\d{11})$', s)
        return match.group(1) if match else s

    # Engine 1: Master Data
    elig_df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    elig_df.columns = [c.strip().lower() for c in elig_df.columns]
    g_col = next((c for c in elig_df.columns if 'geo' in c or 'tract' in c), elig_df.columns[0])
    elig_df['GEOID'] = elig_df[g_col].apply(clean_geoid)
    
    # Engine 2: Demographics
    demo_df = pd.read_csv("Louisiana_All_Tracts_Demographics.csv")
    demo_df.columns = [c.strip().lower() for c in demo_df.columns]
    g_col_d = next((c for c in demo_df.columns if 'geo' in c or 'tract' in c), demo_df.columns[0])
    demo_df['GEOID'] = demo_df[g_col_d].apply(clean_geoid)
    
    # Merge
    m = pd.merge(elig_df, demo_df, on="GEOID", how="left", suffixes=('', '_demo'))

    # Census Variable Mapping
    mapping = {
        's1701_c03_001e': 'poverty_rate',
        's1701_c01_001e': 'pop_total',
        'b19113_001e': 'med_hh_income',
        's2301_c04_001e': 'unemp_rate' 
    }
    m = m.rename(columns=mapping)

    # Convert to numeric
    for met in ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']:
        if met in m.columns:
            m[met] = pd.to_numeric(m[met].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # Engine 3: Anchors
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = [c.strip().lower() for c in a.columns]
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    # GeoJSON Logic (Using the recommended 2024 Cartographic file)
    try:
        with open("la_tracts_2024.json") as f: g = json.load(f)
    except:
        # Fallback to previous name if you haven't renamed it yet
        with open("tl_2025_22_tract.json") as f: g = json.load(f)
    
    centroids = {}
    for feature in g['features']:
        props = feature['properties']
        gid = props.get('GEOID') or props.get('geoid')
        geom = feature['geometry']
        coords = np.array(geom['coordinates'][0]) if geom['type'] == 'Polygon' else np.array(geom['coordinates'][0][0])
        centroids[gid] = [np.mean(coords[:, 1]), np.mean(coords[:, 0])]
    
    m['lat'] = m['GEOID'].map(lambda x: centroids.get(x, [0,0])[0])
    m['lon'] = m['GEOID'].map(lambda x: centroids.get(x, [0,0])[1])
    
    return m, g, a

master_df, la_geojson, anchor_df = load_data()

# --- HIGHLIGHT LOGIC ---
# Tracks highlighted green are only those eligible for the Opportunity Zone 2.0.
# We look for a column indicating OZ 2.0 eligibility (usually 1 for yes, 0 for no)
elig_col = next((c for c in master_df.columns if 'eligible' in c and 'nmtc' not in c), None)

if elig_col:
    # Ensure it's numeric for the color scale
    master_df[elig_col] = pd.to_numeric(master_df[elig_col], errors='coerce').fillna(0).astype(int)
else:
    # Default placeholder if column is missing
    master_df['is_eligible_oz2'] = 0
    elig_col = 'is_eligible_oz2'

# Parish cleaning for display
p_col = next((c for c in master_df.columns if 'name' in c), 'GEOID')
master_df['display_parish'] = master_df[p_col].str.extract(r'([^,]+ Parish)', expand=False).fillna("Louisiana")

# Filtering
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- QUOTA ---
try:
    recs = conn.read(worksheet="Sheet1", ttl=0)
    target_count = len(master_df[master_df[elig_col] == 1])
    q_limit = max(1, int(target_count * 0.25))
    q_rem = q_limit - len(recs[recs['User'] == st.session_state["username"]])
except: recs, q_limit, q_rem = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification"]), 1, 1

# --- INTERFACE ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    sel_p = st.selectbox("Filter Parish", ["All"] + sorted(master_df['display_parish'].unique().tolist()))
    m_df = master_df.copy()
    if sel_p != "All": m_df = m_df[m_df['display_parish'] == sel_p]

    # --- MAP HIGHLIGHTING ENGINE ---
    # 0 = Grey (Ineligible), 1 = Green (Eligible)
    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color=elig_col, 
        color_continuous_scale=[(0, "#D3D3D3"), (1, "#28a745")],
        range_color=[0, 1],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.7, hover_data=["GEOID", "display_parish"]
    )
    
    if not anchor_df.empty:
        fig.add_scattermapbox(lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers', marker=dict(size=8, color='#007bff'), text=anchor_df['name'], name="Anchors")
    
    fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')
    
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state["selected_tract"] = map_event["selection"]["points"][0]["location"]

with c2:
    sid = st.session_state["selected_tract"]
    selected_data = master_df[master_df['GEOID'] == sid]
    
    if not selected_data.empty:
        row = selected_data.iloc[0]
        status = "✅ Eligible" if row[elig_col] == 1 else "❌ Ineligible"
        st.markdown(f"### 📊 Tract {sid}")
        st.markdown(f"**Status:** {status}")
        
        m1, m2 = st.columns(2)
        m1.metric("Population", f"{row.get('pop_total', 0):,.0f}")
        m2.metric("Median Income", f"${row.get('med_hh_income', 0):,.0f}")

        st.divider()
        with st.form("rec_form", clear_on_submit=True):
            cat = st.selectbox("Category", ["Housing", "Health", "Commercial", "Infrastructure"])
            just = st.text_area("Justification")
            if st.form_submit_button("Submit Recommendation"):
                new_rec = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": sid, "Category": cat, "Justification": just}])
                conn.update(worksheet="Sheet1", data=pd.concat([recs, new_rec], ignore_index=True))
                st.success("Saved!"); st.cache_data.clear(); st.rerun()
    else:
        st.info("Select a tract to see data.")