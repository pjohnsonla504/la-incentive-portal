import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. AMERICAN DYNAMISM DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | American Dynamism", layout="wide")

st.markdown("""
    <style>
    /* Main Background and Text */
    .stApp {
        background-color: #050a14;
        color: #ffffff;
    }
    
    /* Global Typography */
    html, body, [class*="css"]  {
        font-family: 'Inter', sans-serif;
    }

    /* Metric Card Styling */
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #00ff88 !important; /* Neon Accent */
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #94a3b8 !important;
    }
    .stMetric {
        background-color: #0f172a;
        padding: 15px;
        border-radius: 4px;
        border: 1px solid #1e293b;
        transition: border 0.3s ease;
    }
    .stMetric:hover {
        border: 1px solid #00ff88;
    }

    /* Sidebar/Profile Panel */
    section[data-testid="stSidebar"] {
        background-color: #0f172a;
    }

    /* Primary Button */
    .stButton>button {
        background-color: #00ff88 !important;
        color: #050a14 !important;
        font-weight: 700;
        border-radius: 4px;
        border: none;
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 1px;
    }

    /* Inputs */
    .stTextArea textarea {
        background-color: #0f172a !important;
        color: white !important;
        border: 1px solid #1e293b !important;
    }

    /* Divider */
    hr {
        border-top: 1px solid #1e293b;
    }
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"System Link Failure: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

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
    
    # Load Anchors with Robust Encoding
    try:
        a = pd.read_csv("la_anchors.csv")
    except UnicodeDecodeError:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    
    a.columns = a.columns.str.strip().str.lower()
    a = a.dropna(subset=['lat', 'lon'])

    # Mapping
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
        "home": "Median Home Value",
        "dis": "Disability Population (%)",
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
    st.markdown("<h1 style='text-align: center; color: #00ff88;'>AMERICAN DYNAMISM</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #94a3b8;'>OZ 2.0 STRATEGIC NOMINATION PORTAL</p>", unsafe_allow_html=True)
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

# --- 4. DASHBOARD ---
st.markdown(f"<h2 style='margin-bottom:0px;'>{st.session_state['a_val']} Sector</h2>", unsafe_allow_html=True)
st.markdown(f"<p style='color: #94a3b8;'>Welcome, Agent {st.session_state['username']}</p>", unsafe_allow_html=True)

col_map, col_side = st.columns([0.6, 0.4])

with col_map:
    fig = go.Figure()
    
    # Dark Mode Map Layer
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0, 255, 136, 0.4)"]], # Neon Green
        showscale=False, marker_line_width=0.3, marker_line_color="#1e293b"
    ))
    
    # High-Visibility Anchors
    if not anchor_df.empty:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=10, color='#ffffff', symbol='circle'), # Solid white for contrast
            text=anchor_df['name'], hoverinfo='text', name="Anchors"
        ))
    
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 30.8, "lon": -91.8}, zoom=7),
        height=700, margin={"r":0,"t":0,"l":0,"b":0}
    )
    
    select_data = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if select_data and select_data.get("selection") and select_data["selection"].get("points"):
        st.session_state["selected_tract"] = str(select_data["selection"]["points"][0].get("location")).split('.')[0].zfill(11)

with col_side:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"<h3 style='color:#00ff88;'>TRACT {sid}</h3>", unsafe_allow_html=True)
        st.markdown(f"**PARISH:** {row.get('Parish')}  |  **METRO:** {row.get('Rural or Urban')}")
        
        st.divider()
        
        # 8 METRICS IN DYNAMISM STYLE
        m_cols = st.columns(2)
        m_cols[0].metric("MEDIAN HOME VALUE", safe_num(row.get(M_MAP["home"]), True))
        m_cols[1].metric("DISABILITY POP", safe_num(row.get(M_MAP["dis"])))
        
        m_cols = st.columns(2)
        m_cols[0].metric("AGE 65+", safe_num(row.get(M_MAP["pop65"])))
        m_cols[1].metric("LABOR FORCE", safe_num(row.get(M_MAP["labor"])))
        
        m_cols = st.columns(2)
        m_cols[0].metric("UNEMPLOYMENT", safe_num(row.get(M_MAP["unemp"])))
        m_cols[1].metric("HS GRADUATE+", safe_num(row.get(M_MAP["hs"])))
        
        m_cols = st.columns(2)
        m_cols[0].metric("BACHELOR'S+", safe_num(row.get(M_MAP["bach"])))
        m_cols[1].metric("BROADBAND", safe_num(row.get(M_MAP["web"])))

        st.divider()
        st.markdown("##### ⚓ PROXIMITY: TOP 10 ANCHORS")
        t_coord = tract_centers.get(sid)
        if t_coord and not anchor_df.empty:
            a_copy = anchor_df.copy()
            a_copy['dist'] = a_copy.apply(lambda x: calculate_distance(t_coord['lat'], t_coord['lon'], x['lat'], x['lon']), axis=1)
            for _, a in a_copy.sort_values('dist').head(10).iterrows():
                st.markdown(f"<p style='margin-bottom:0px; font-size:0.9rem;'><b>{a['dist']:.1f} MI</b> — {a['name']}</p>", unsafe_allow_html=True)
    else:
        st.info("SELECT A TARGET TRACT ON THE MAP")

# --- 5. NOMINATION ACTION ---
st.divider()
if not match.empty:
    st.subheader("NOMINATION JUSTIFICATION")
    note = st.text_area("Input strategic reasoning for tract selection...")
    if st.button("EXECUTE NOMINATION"):
        st.success(f"Tract {sid} Nomination Logged.")

st.markdown("### NOMINATION HISTORY")
try:
    hist = conn.read(worksheet="Sheet1", ttl=0)
    st.dataframe(hist[hist['User'] == st.session_state["username"]], use_container_width=True)
except:
    st.caption("No historical records found.")