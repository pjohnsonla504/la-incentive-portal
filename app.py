import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- HELPERS ---
def safe_float(val):
    try:
        if pd.isna(val) or val == '' or val == 'N/A': return 0.0
        s = str(val).replace('$', '').replace(',', '').replace('%', '').strip()
        return float(s)
    except: return 0.0

def safe_int(val):
    return int(safe_float(val))

def robust_geoid(val):
    """Fixes scientific notation (2.2035E+10) and ensures 11-digit padding."""
    try:
        if pd.isna(val) or str(val).strip() == "": return ""
        # Handle scientific notation by converting to float then int
        f_val = float(str(val).replace(',', '').strip())
        return str(int(f_val)).zfill(11)
    except:
        return str(val).split('.')[0].strip().zfill(11)

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username"].strip()
            p = str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    return
            st.session_state["password_correct"] = False
            st.error("Invalid username or password")
        except Exception as e:
            st.error(f"Error connecting to database: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
            .stApp { background-color: #0b0f19 !important; font-family: 'Inter', sans-serif; }
            div[data-testid="stVerticalBlock"] > div:has(input) {
                background-color: #111827; padding: 40px; border-radius: 15px;
                border: 1px solid #1e293b; box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }
            label { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.05em; }
            input { background-color: #0b0f19 !important; color: white !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; }
            button[kind="primary"], .stButton > button { background-color: #4ade80 !important; color: #0b0f19 !important; font-weight: 900 !important; border: none !important; height: 3em !important; margin-top: 10px; }
            </style>
        """, unsafe_allow_html=True)

        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<div style='text-align: center; margin-bottom: 2rem;'><h1 style='color: white; font-weight: 900;'>OZ 2.0 Portal</h1></div>", unsafe_allow_html=True)
            with st.container():
                st.text_input("Username", key="username")
                st.text_input("Password", type="password", key="password")
                st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING & FROZEN NAV ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        
        .nav-container {
            position: fixed; top: 0; left: 0; width: 100%;
            background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b;
            padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px);
        }
        /* Force text to stay white and override browser link defaults */
        .nav-link, .nav-link:link, .nav-link:visited {
            color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; transition: color 0.3s ease;
        }
        .nav-link:hover, .nav-link:active { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }

        /* Component Styles */
        div[data-baseweb="select"] > div { background-color: #ffffff !important; border-radius: 6px !important; }
        div[data-baseweb="select"] * { color: #0f172a !important; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; line-height: 1.1; }
        .benefit-card { background-color: #111827; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; transition: all 0.3s ease; }
        .benefit-card:hover { border-color: #4ade80; }
        .metric-card { background-color: #111827; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; }
        .view-site-btn { display: block; background-color: #4ade80; color: #0b0f19 !important; padding: 6px 0; border-radius: 4px; text-decoration: none !important; font-size: 0.7rem; font-weight: 900; text-align: center; margin-top: 8px; }
        </style>

        <div class="nav-container">
            <a class="nav-link" href="#section-1">Overview</a>
            <a class="nav-link" href="#section-2">Benefits</a>
            <a class="nav-link" href="#section-3">Strategy</a>
            <a class="nav-link" href="#section-4">Best Practices</a>
            <a class="nav-link" href="#section-5">Mapping</a>
            <a class="nav-link" href="#section-6">Report</a>
        </div>
    """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 3956 * 2 * asin(sqrt(a))

    @st.cache_data(ttl=3600)
    def load_assets():
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        def read_csv_with_fallback(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)

        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
        
        # --- CLEANING & ROBUST GEOMATCH ---
        master['Parish'] = master['Parish'].astype(str).str.strip()
        master['Region'] = master['Region'].astype(str).str.strip()
        master['geoid_str'] = master['11-digit FIP'].apply(robust_geoid)
        
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )

        pov_col = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
        mfi_ratio_col = "Percentage of Benchmarked Median Family Income"
        unemp_ratio_col = "Unemployment Ratio"

        def calc_nmtc_status(row):
            pov = safe_float(row.get(pov_col, 0))
            mfi_pct = safe_float(row.get(mfi_ratio_col, 0)) if mfi_ratio_col in row else 100
            unemp_ratio = safe_float(row.get(unemp_ratio_col, 0)) if unemp_ratio_col in row else 1.0
            if pov > 40 or mfi_pct <= 40 or unemp_ratio >= 2.5: return "Deep Distress"
            elif pov >= 20 or mfi_pct <= 80 or unemp_ratio >= 1.5: return "Eligible"
            return "Ineligible"

        master['NMTC_Calculated'] = master.apply(calc_nmtc_status, axis=1)
        anchors = read_csv_with_fallback("la_anchors.csv")
        
        centers = {}
        id_key = "GEOID"
        if gj:
            id_key = "GEOID" if "GEOID" in gj['features'][0]['properties'] else "GEOID20"
            for feature in gj['features']:
                geoid = feature['properties'].get(id_key)
                try:
                    geom = feature['geometry']
                    pts = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers, id_key

    gj, master_df, anchors_df, tract_centers, geo_id_key = load_assets()

    def get_zoom_center(geoids):
        if not geoids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.0
        lats, lons = [], []
        for feature in gj['features']:
            if feature['properties'].get(geo_id_key) in geoids:
                geom = feature['geometry']
                coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
                lons.extend(np.array(coords)[:, 0]); lats.extend(np.array(coords)[:, 1])
        if not lats: return {"lat": 30.9, "lon": -91.8}, 6.0
        center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
        diff = max(max(lats)-min(lats), max(lons)-min(lons))
        zoom = 11.5 if diff < 0.1 else 9.5 if diff < 0.4 else 6.5
        return center, zoom

    def render_map_go(df):
        map_df = df.copy()
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        map_df['Color_Cat'] = map_df.apply(lambda r: 2 if r['geoid_str'] in selected_geoids else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        
        focus_ids = {st.session_state["active_tract"]} if st.session_state.get("active_tract") in map_df['geoid_str'].values else set(map_df['geoid_str'].tolist())
        center, zoom = get_zoom_center(focus_ids)
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Cat'],
            featureidkey=f"properties.{geo_id_key}",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], zmin=0, zmax=2,
            showscale=False, marker=dict(opacity=0.7, line=dict(width=0.5, color='white')),
            selectedpoints=map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist() if st.session_state["active_tract"] else None
        ))
        fig.update_layout(mapbox=dict(style="carto-positron", zoom=zoom, center=center), margin={"r":0,"t":0,"l":0,"b":0}, height=600, uirevision="constant")
        return fig

    # --- CONTENT SECTIONS 1-4 ---
    st.markdown("<div id='section-1' class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-2' class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Benefit Framework</div></div>", unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Deferred taxes on capital gains until 2030.</p></div>", unsafe_allow_html=True)
    with b_col2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>10% to 30% basis increase depending on fund type.</p></div>", unsafe_allow_html=True)
    with b_col3: st.markdown("<div class='benefit-card'><h3>10-Year Exclusion</h3><p>Permanent exclusion of new gains after 10 years.</p></div>", unsafe_allow_html=True)

    st.markdown("<div id='section-3' class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Tract Advocacy</div></div>", unsafe_allow_html=True)
    st.markdown("<div id='section-4' class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div></div>", unsafe_allow_html=True)

    # --- SECTION 5: MAPPING ---
    st.markdown("<div id='section-5' class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping</div></div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        reg_list = sorted([x for x in master_df['Region'].unique() if str(x) != 'nan'])
        selected_region = st.selectbox("Region", ["All Louisiana"] + reg_list)
    
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    
    with f_col2:
        par_list = sorted([x for x in filtered_df['Parish'].unique() if str(x) != 'nan'])
        selected_parish = st.selectbox("Parish", ["All in Region"] + par_list)
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    
    with f_col3:
        tract_list = ["Search Tract..."] + sorted(filtered_df['geoid_str'].tolist())
        selected_search = st.selectbox("Find Census Tract", tract_list)
        if selected_search != "Search Tract..." and st.session_state["active_tract"] != selected_search:
            st.session_state["active_tract"] = selected_search
            st.rerun()

    c_map = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="main_map")
    if c_map and "selection" in c_map and c_map["selection"]["points"]:
        new_id = str(c_map["selection"]["points"][0]["location"])
        if st.session_state["active_tract"] != new_id:
            st.session_state["active_tract"] = new_id
            st.rerun()

    # --- TRACT DETAILS & REPORT ---
    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr].iloc[0]
        st.markdown(f"### {row['Parish']} - {curr}")
        # (Metric and Anchor display logic here)

    st.markdown("<div id='section-6'></div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.write("### Recommendation Report")
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True)