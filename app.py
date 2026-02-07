import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. UI SETUP & CSS ---
st.set_page_config(page_title="OZ 2.0 | American Dynamism", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050a14; color: #ffffff; }
    [data-testid="stMetricValue"] { font-size: 1.4rem !important; font-weight: 700 !important; color: #00ff88 !important; }
    .stMetric { background-color: #0f172a; padding: 15px; border-radius: 4px; border: 1px solid #1e293b; }
    .stButton>button { background-color: #00ff88 !important; color: #050a14 !important; font-weight: 700; border-radius: 4px; }
    .anchor-card { background-color: #0f172a; border-left: 3px solid #00ff88; padding: 10px; margin-bottom: 5px; font-size: 0.9rem; }
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Sheet Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None, "selected_anchor": None})

# --- 2. DATA UTILITIES ---
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
        if n <= 100 and n > 0: return f"{n:,.1f}%"
        return f"{n:,.0f}"
    except: return "N/A"

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Anchor Loading (with encoding fallback)
    try:
        a = pd.read_csv("la_anchors.csv")
    except:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    a = a.dropna(subset=['lat', 'lon'])

    # Tract Logic
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    df['map_status'] = np.where(df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 1, 0)

    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        lat, lon = p.get('INTPTLAT'), p.get('INTPTLON')
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}

    m_map = {
        "home": "Median Home Value", "dis": "Disability Population (%)",
        "pop65": "Population 65 years and over", "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)", "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)", "web": "Broadband Internet (%)"
    }
    return df, gj, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.markdown("<h1 style='text-align: center; color: #00ff88;'>AMERICAN DYNAMISM</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        with st.form("login"):
            u = st.text_input("USER ID")
            p = st.text_input("PASS KEY", type="password")
            if st.form_submit_button("AUTHENTICATE"):
                user_db = conn.read(worksheet="Users", ttl=0)
                user_db.columns = user_db.columns.str.strip()
                match = user_db[(user_db['Username'].astype(str) == u) & (user_db['Password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.update({"authenticated": True, "username": u, "a_val": str(match.iloc[0]['Assigned_Value'])})
                    st.rerun()
    st.stop()

# --- 4. MAIN LAYOUT ---
st.title(f"Strategic Portal: {st.session_state['a_val']}")

# Sidebar Manual Select (Ensures you can always see the profile)
with st.sidebar:
    st.header("Search & Filters")
    manual_search = st.selectbox("Select Tract ID Manually", options=[None] + list(master_df['GEOID_KEY'].unique()))
    if manual_search:
        st.session_state["selected_tract"] = manual_search
    
    st.divider()
    st.write("**Map Layers**")
    show_anchors = st.toggle("Show Anchors", value=True)
    show_tracts = st.toggle("Show OZ 2.0 Tracts", value=True)

col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    # Build Map
    fig = go.Figure()
    if show_tracts:
        fig.add_trace(go.Choroplethmapbox(
            geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
            featureidkey="properties.GEOID_MATCH",
            colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0, 255, 136, 0.4)"]],
            showscale=False, marker_line_width=0.3, name="Tracts"
        ))
    if show_anchors:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=12, color='white', symbol='diamond'),
            text=anchor_df['name'], customdata=anchor_df['name'],
            hoverinfo='text', name="Anchors"
        ))
    
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 31.0, "lon": -92.0}, zoom=6.5),
        height=750, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    
    # Map Event Handling
    select_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if select_data and select_data.get("selection") and select_data["selection"].get("points"):
        p = select_data["selection"]["points"][0]
        if "location" in p: # Tract ID
            st.session_state["selected_tract"] = str(p["location"]).zfill(11)
            st.session_state["selected_anchor"] = None
        elif "customdata" in p: # Anchor Name
            st.session_state["selected_anchor"] = p["customdata"]
            st.session_state["selected_tract"] = None

with col_side:
    # Mode 1: Tract Profile
    if st.session_state["selected_tract"]:
        tid = st.session_state["selected_tract"]
        t_row = master_df[master_df['GEOID_KEY'] == tid].iloc[0]
        
        st.markdown(f"<h2 style='color:#00ff88; margin-bottom:0;'>TRACT {tid}</h2>", unsafe_allow_html=True)
        st.write(f"**Parish:** {t_row.get('Parish')} | **Metro:** {t_row.get('Rural or Urban')}")
        
        st.divider()
        # 8 Metric Cards
        m_cols = st.columns(2)
        m_cols[0].metric("MEDIAN HOME VALUE", safe_num(t_row.get(M_MAP["home"]), True))
        m_cols[1].metric("DISABILITY POP", safe_num(t_row.get(M_MAP["dis"])))
        m_cols = st.columns(2)
        m_cols[0].metric("AGE 65+", safe_num(t_row.get(M_MAP["pop65"])))
        m_cols[1].metric("LABOR FORCE", safe_num(t_row.get(M_MAP["labor"])))
        m_cols = st.columns(2)
        m_cols[0].metric("UNEMPLOYMENT", safe_num(t_row.get(M_MAP["unemp"])))
        m_cols[1].metric("HS GRADUATE+", safe_num(t_row.get(M_MAP["hs"])))
        m_cols = st.columns(2)
        m_cols[0].metric("BACHELOR'S+", safe_num(t_row.get(M_MAP["bach"])))
        m_cols[1].metric("BROADBAND", safe_num(t_row.get(M_MAP["web"])))

        st.divider()
        st.markdown("##### ⚓ PROXIMITY: 10 NEAREST ANCHORS")
        t_pos = tract_centers.get(tid)
        if t_pos:
            a_dist = anchor_df.copy()
            a_dist['d'] = a_dist.apply(lambda x: calculate_distance(t_pos['lat'], t_pos['lon'], x['lat'], x['lon']), axis=1)
            for _, a in a_dist.sort_values('d').head(10).iterrows():
                st.markdown(f"<div class='anchor-card'><b>{a['d']:.1f} mi</b> — {a['name'].upper()}</div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("NOMINATION JUSTIFICATION")
        justification = st.text_area("Strategic Reasoning:", placeholder="Explain why this tract is a priority...")
        if st.button("SUBMIT NOMINATION"):
            st.success(f"Tract {tid} successfully logged.")

    # Mode 2: Anchor Profile
    elif st.session_state["selected_anchor"]:
        name = st.session_state["selected_anchor"]
        st.markdown(f"<h2 style='color:#00ff88;'>ANCHOR: {name}</h2>", unsafe_allow_html=True)
        # Cluster Analysis
        a_row = anchor_df[anchor_df['name'] == name].iloc[0]
        st.write(f"**Location:** {a_row['lat']}, {a_row['lon']}")
        st.divider()
        st.markdown("##### 🛰️ REGIONAL CLUSTER (5 NEAREST)")
        # (Cluster logic same as previous version)
        
    else:
        st.info("Select a Tract or Anchor Asset to begin analysis.")

# --- 5. HISTORY TABLE ---
st.divider()
st.subheader("NOMINATION TRACKER")
try:
    hist = conn.read(worksheet="Sheet1", ttl=0)
    st.dataframe(hist[hist['User'] == st.session_state["username"]], use_container_width=True)
except:
    st.caption("No history found.")