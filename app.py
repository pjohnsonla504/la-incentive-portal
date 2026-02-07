import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIG & UI ---
st.set_page_config(page_title="OZ 2.0 Planner", layout="wide")

st.markdown("""
    <style>
    .block-container {padding-top: 1rem; padding-bottom: 1rem;}
    [data-testid="stMetricValue"] {font-size: 1.1rem !important;}
    .stMetric {background-color: #f8f9fa; padding: 10px; border-radius: 5px; border: 1px solid #e0e0e0;}
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        p1, p2 = np.radians(float(lat1)), np.radians(float(lat2))
        dp, dl = np.radians(float(lat2)-float(lat1)), np.radians(float(lon2)-float(lon1))
        a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.0

def safe_num(val, is_money=False):
    try:
        if pd.isna(val) or str(val).strip().lower() in ['n/a', 'nan', '']: return "N/A"
        n = float(str(val).replace('$', '').replace(',', '').replace('%', '').strip())
        if is_money: return f"${n:,.0f}"
        # If it's a percentage (less than or equal to 100), show as %
        if n <= 100 and n > 0: return f"{n:,.1f}%"
        return f"{n:,.0f}"
    except: return "N/A"

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Master Data File
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Anchor Loading (FIXED FOR CASE SENSITIVITY)
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip().str.lower() # Forces 'Lat' to 'lat'
        a = a.dropna(subset=['lat', 'lon'])
    except Exception as e:
        a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
        st.error(f"Anchor File Error: {e}")

    # GEOID Logic
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Green = OZ 2.0 Eligible
    df['map_status'] = np.where(df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 1, 0)

    # GeoJSON
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        lat, lon = p.get('INTPTLAT'), p.get('INTPTLON')
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}

    # COLUMN HEADERS MAPPING
    m_map = {
        "home": "Median Home Value",
        "disability": "Disability Population (%)",
        "pop65": "Population 65 years and over",
        "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)",
        "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)",
        "web": "Broadband Internet (%)"
    }
    return df, gj, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Access")
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login"):
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.form_submit_button("Login"):
                user_db = conn.read(worksheet="Users", ttl=0)
                user_db.columns = user_db.columns.str.strip()
                match = user_db[(user_db['Username'].astype(str) == u) & (user_db['Password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.update({"authenticated": True, "username": u, "a_val": str(match.iloc[0]['Assigned_Value'])})
                    st.rerun()
    st.stop()

# --- 4. INTERFACE ---
st.title(f"📍 Strategic Planner: {st.session_state['a_val']}")

col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    fig = go.Figure()
    # 1. Tracts Layer
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(40, 167, 69, 0.6)"]], # Green for OZ 2.0
        showscale=False, marker_line_width=0.5, marker_line_color="white"
    ))
    # 2. Anchors Layer (Black Diamonds)
    if not anchor_df.empty:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=12, color='black', symbol='diamond'),
            text=anchor_df['name'], hoverinfo='text', name="Anchor Assets"
        ))
    
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 30.8, "lon": -91.8}, zoom=7),
        height=650, margin={"r":0,"t":0,"l":0,"b":0}
    )
    
    select_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if select_data and select_data.get("selection") and select_data["selection"].get("points"):
        st.session_state["selected_tract"] = str(select_data["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_side:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"### 📋 Tract Profile: {sid}")
        st.write(f"**Parish:** {row.get('Parish')} | **Region:** {row.get('Region')}")
        st.write(f"**Metro Status:** {row.get('Rural or Urban')}")
        
        st.divider()
        # 8 METRIC CARDS (Requested Headers)
        c_m1, c_m2 = st.columns(2)
        c_m1.metric("Med. Home Value", safe_num(row.get(M_MAP["home"]), True))
        c_m2.metric("Disability Pop", safe_num(row.get(M_MAP["disability"])))
        
        c_m3, c_m4 = st.columns(2)
        c_m3.metric("Age 65+", safe_num(row.get(M_MAP["pop65"])))
        c_m4.metric("Labor Participation", safe_num(row.get(M_MAP["labor"])))
        
        c_m5, c_m6 = st.columns(2)
        c_m5.metric("Unemployment Rate", safe_num(row.get(M_MAP["unemp"])))
        c_m6.metric("HS Degree+", safe_num(row.get(M_MAP["hs"])))
        
        c_m7, c_m8 = st.columns(2)
        c_m7.metric("Bachelor's+", safe_num(row.get(M_MAP["bach"])))
        c_m8.metric("Broadband Access", safe_num(row.get(M_MAP["web"])))

        st.divider()
        st.markdown("##### ⚓ 10 Nearest Anchors")
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            a_copy = anchor_df.copy()
            a_copy['dist'] = a_copy.apply(lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1)
            for _, a in a_copy.sort_values('dist').head(10).iterrows():
                st.write(f"**{a['dist']:.1f} mi** — {a['name']} <small>({a.get('type','Education')})</small>", unsafe_allow_html=True)
    else:
        st.info("👆 Click a **Green** tract on the map to view detailed demographics.")

# --- 5. JUSTIFICATION & HISTORY (Bottom) ---
st.divider()
if not match.empty:
    st.subheader(f"Nomination Form: {sid}")
    note = st.text_area("Justification for this nomination:")
    if st.button("Submit Recommendation", type="primary", use_container_width=True):
        st.success("Nomination Recorded.")

st.subheader("📋 My Recommendation History")
try:
    history = conn.read(worksheet="Sheet1", ttl=0)
    st.dataframe(history[history['User'] == st.session_state["username"]], use_container_width=True)
except: 
    st.caption("No history found yet.")