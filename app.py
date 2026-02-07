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
    [data-testid="stMetricValue"] {font-size: 1.3rem !important;}
    .stMetric {background-color: #f8f9fa; padding: 8px; border-radius: 5px; border: 1px solid #e0e0e0;}
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# Math Helpers
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
        return f"${n:,.0f}" if is_money else f"{n:,.0f}"
    except: return "N/A"

# --- 2. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Primary Data
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Anchors Data (THE FILE IN QUESTION)
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = a.columns.str.strip()
    except: 
        st.warning("la_anchors.csv not found. Please ensure it is in your repository.")
        a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    # GEOID Matching
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Eligibility Colors
    df['color'] = np.where(df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), "#28a745", "rgba(0,0,0,0)")

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
        "pop": "Estimate!!Total!!Population for whom poverty status is determined",
        "income": "Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)",
        "poverty": "Estimate!!Percent below poverty level!!Population for whom poverty status is determined",
        "pop65": "Population 65 years and over"
    }
    return df, gj, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Access")
    c1, c2, c3 = st.columns([1,2,1])
    with col2 := c2:
        with st.form("login"):
            u = st.text_input("Username").strip()
            p = st.text_input("Password", type="password").strip()
            if st.form_submit_button("Login"):
                user_db = conn.read(worksheet="Users", ttl=0)
                user_db.columns = user_db.columns.str.strip()
                match = user_db[(user_db['Username'].astype(str) == u) & (user_db['Password'].astype(str) == p)]
                if not match.empty:
                    st.session_state.update({"authenticated": True, "username": u, "a_val": str(match.iloc[0]['Assigned_Value'])})
                    st.rerun()
    st.stop()

# --- 4. DATA COUNTER ---
try:
    history = conn.read(worksheet="Sheet1", ttl=0)
    user_history = history[history['User'] == st.session_state["username"]]
except:
    user_history = pd.DataFrame()

# --- 5. INTERFACE ---
st.title(f"📍 Strategic Planner: {st.session_state['a_val']}")
st.write(f"**User:** {st.session_state['username']} | **Submitted:** {len(user_history)}")

col_map, col_side = st.columns([0.6, 0.4])

with col_map:
    # Build Map with Graph Objects for Layer Priority
    fig = go.Figure()
    
    # Layer 1: Tracts
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson,
        locations=master_df['GEOID_KEY'],
        z=np.ones(len(master_df)),
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(40, 167, 69, 0.5)"]],
        showscale=False,
        marker_line_width=0.5,
        hovertext=master_df['GEOID_KEY']
    ))
    
    # Layer 2: Anchors (Drawn LAST to be on TOP)
    if not anchor_df.empty:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'],
            lon=anchor_df['lon'],
            mode='markers',
            marker=dict(size=12, color='black', symbol='diamond'),
            text=anchor_df['name'],
            hoverinfo='text'
        ))
    
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 30.8, "lon": -91.8}, zoom=7),
        height=600, margin={"r":0,"t":0,"l":0,"b":0}
    )
    
    select_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if select_data and select_data.get("selection") and select_data["selection"].get("points"):
        st.session_state["selected_tract"] = str(select_data["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_side:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"### Tract Profile: {sid}")
        st.write(f"**Parish:** {row.get('Parish', 'N/A')}")
        st.write(f"**Region:** {row.get('Region', 'N/A')}")
        st.write(f"**Metro Status:** {row.get('Rural or Urban', 'N/A')}")
        
        m1, m2 = st.columns(2)
        m1.metric("Family Income", safe_num(row.get(M_MAP["income"]), True))
        m2.metric("Poverty Rate", f"{safe_num(row.get(M_MAP['poverty']))}%")
        
        st.divider()
        st.markdown("##### ⚓ 10 Nearest Anchors")
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            a_copy = anchor_df.copy()
            a_copy['dist'] = a_copy.apply(lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1)
            for _, a in a_copy.sort_values('dist').head(10).iterrows():
                st.write(f"**{a['dist']:.1f} mi** — {a['name']}")
    else:
        st.info("Select an eligible tract to view details.")

# --- 6. JUSTIFICATION (Below Map) ---
st.divider()
if not match.empty:
    st.subheader(f"Nomination Form: {sid}")
    note = st.text_area("Provide justification for this tract nomination:", height=80)
    if st.button("Submit Nomination"):
        st.success(f"Nomination for {sid} has been submitted!")

# --- 7. HISTORY TABLE ---
st.subheader("📋 My Recommendation History")
st.dataframe(user_history, use_container_width=True)