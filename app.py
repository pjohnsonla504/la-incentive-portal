import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import json
import os
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
            .login-header { text-align: center; margin-bottom: 2rem; }
            </style>
        """, unsafe_allow_html=True)

        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("""
                <div class="login-header">
                    <p style='color: #4ade80; font-weight: 900; letter-spacing: 0.2em; font-size: 0.8rem; margin-bottom: 0;'>SECURE ACCESS</p>
                    <h1 style='color: white; font-weight: 900; margin-top: 0;'>OZ 2.0 Portal</h1>
                </div>
            """, unsafe_allow_html=True)
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
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .nav-link:hover { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; margin-bottom: 20px; line-height: 1.1; }
        .narrative-text { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; min-height: 280px; }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 15px; font-weight: 800; font-size: 1.3rem; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        </style>

        <div class="nav-container">
            <a class="nav-link" href="#section-1">Overview</a>
            <a class="nav-link" href="#section-2">Benefits</a>
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
        
        def read_csv_robust(path):
            for enc in ['utf-8-sig', 'latin1', 'cp1252']:
                try: 
                    df = pd.read_csv(path, encoding=enc)
                    df.columns = df.columns.str.strip()
                    return df
                except: continue
            return pd.read_csv(path)

        # Using V2 File and GEOID column
        master = read_csv_robust("Opportunity Zones 2.0 - Master Data File (V2).csv")
        
        if 'GEOID' in master.columns:
            master['geoid_str'] = master['GEOID'].astype(str).str.split('.').str[0].str.zfill(11)
        else:
            st.error(f"Critical Error: 'GEOID' column not found. Columns found: {list(master.columns)}")
            st.stop()

        # Logic for highlighting Eligible tracts
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        if elig_col in master.columns:
            master['Eligibility_Status'] = master[elig_col].apply(
                lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1', 'true'] else 'Ineligible'
            )
        else:
            master['Eligibility_Status'] = 'Ineligible'

        # NMTC Distress Logic
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

        anchors = read_csv_robust("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        
        centers = {}
        if gj:
            id_key = "GEOID" if "GEOID" in str(gj['features'][0]['properties']) else "GEOID20"
            for feature in gj['features']:
                geoid = feature['properties'].get(id_key)
                try:
                    geom = feature['geometry']
                    pts = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def get_zoom_center(geoids):
        if not geoids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.0
        lats, lons = [], []
        id_key = "GEOID" if "GEOID" in str(gj['features'][0]['properties']) else "GEOID20"
        for feature in gj['features']:
            if feature['properties'].get(id_key) in geoids:
                geom = feature['geometry']
                coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
                pts = np.array(coords)
                lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
        if not lats: return {"lat": 30.9, "lon": -91.8}, 6.0
        return {"lat": (min(lats)+max(lats))/2, "lon": (min(lons)+max(lons))/2}, 8.5

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        map_df['Color_Category'] = map_df.apply(lambda r: 2 if r['geoid_str'] in selected_geoids else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        
        focus_geoids = {st.session_state["active_tract"]} if st.session_state.get("active_tract") else set(map_df['geoid_str'])
        center, zoom = get_zoom_center(focus_geoids)
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], 
            zmin=0, zmax=2, showscale=False, marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))

        # Add Anchor Pins
        color_palette = px.colors.qualitative.Bold
        for i, a_type in enumerate(sorted(anchors_df['Type'].unique())):
            t_data = anchors_df[anchors_df['Type'] == a_type]
            fig.add_trace(go.Scattermapbox(
                lat=t_data['Lat'], lon=t_data['Lon'], mode='markers',
                marker=go.scattermapbox.Marker(size=10, color=color_palette[i % len(color_palette)]),
                name=a_type, text=t_data['Name'], visible='legendonly'
            ))

        fig.update_layout(mapbox=dict(style="carto-positron", zoom=zoom, center=center), margin={"r":0,"t":0,"l":0,"b":0}, height=650, uirevision='constant')
        return fig

    # --- CONTENT SECTIONS ---
    st.markdown("<div id='section-1' class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div><div class='narrative-text'>Strategically identifying and recommending census tracts for the 2025 Opportunity Zone expansion.</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-2' class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Benefit Framework</div><div class='narrative-text'>Opportunity Zones encourage long-term investment via capital gains deferral, basis step-up, and total gain exclusion.</div></div>", unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Investors may defer taxes on capital gains reinvested in a QOF for up to five years.</p></div>", unsafe_allow_html=True)
    with b_col2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Urban tracts receive a 10% basis increase; Rural Opportunity Funds (QROF) receive a 30% increase.</p></div>", unsafe_allow_html=True)
    with b_col3: st.markdown("<div class='benefit-card'><h3>10-Year Exclusion</h3><p>New gains generated from the sale of an OZ investment held for 10+ years are permanently excluded from taxable income.</p></div>", unsafe_allow_html=True)

    # --- MAPPING SECTION ---
    st.markdown("<div id='section-5' class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping</div></div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    with f_col2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    with f_col3:
        tract_list = ["Search Tract GEOID..."] + sorted(filtered_df['geoid_str'].tolist())
        selected_search = st.selectbox("Find Census Tract", tract_list)
        if selected_search != "Search Tract GEOID...":
            st.session_state["active_tract"] = selected_search

    map_sel = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="main_map")
    if map_sel and "selection" in map_sel and map_sel["selection"]["points"]:
        st.session_state["active_tract"] = str(map_sel["selection"]["points"][0]["location"])
        st.rerun()

    if st.session_state.get("active_tract"):
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr].iloc[0]
        st.markdown(f"<h2 style='color:#4ade80;'>TRACT {curr} - {str(row['Parish']).upper()}</h2>", unsafe_allow_html=True)
        
        d_col1, d_col2 = st.columns([0.6, 0.4], gap="large")
        with d_col1:
            st.markdown("<p style='color:#94a3b8; font-weight:700; font-size:0.75rem; letter-spacing:0.1em;'>TRACT DEMOGRAPHICS</p>", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3), st.columns(3), st.columns(3)
            m1[0].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            m1[1].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['NMTC_Calculated'] != 'Ineligible' else 'NO'}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            m1[2].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['NMTC_Calculated'] == 'Deep Distress' else 'NO'}</div><div class='metric-label'>Deep Distress</div></div>", unsafe_allow_html=True)
            m2[0].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get(pov_col, 0)):.1f}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            m2[1].markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>MFI</div></div>", unsafe_allow_html=True)
            m2[2].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            
            rec_cat = st.selectbox("Recommendation Category", ["Housing", "Business", "Infrastructure", "Mixed-Use"])
            justification = st.text_area("Justification")
            if st.button("Add to Report", use_container_width=True, type="primary"):
                st.session_state["session_recs"].append({"Tract": curr, "Parish": row['Parish'], "Category": rec_cat, "Justification": justification})
                st.toast("Tract Added!"); st.rerun()

        with d_col2:
            st.markdown("<p style='color:#94a3b8; font-weight:700; font-size:0.75rem; letter-spacing:0.1em;'>NEARBY ASSETS</p>", unsafe_allow_html=True)
            if curr in tract_centers:
                lon, lat = tract_centers[curr]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                for _, a in anchors_df.sort_values('dist').head(5).iterrows():
                    st.markdown(f"<div style='background:#111827; border:1px solid #1e293b; padding:10px; border-radius:8px; margin-bottom:8px;'><div style='color:#4ade80; font-size:0.7rem; font-weight:700;'>{a['Type']}</div><div style='font-weight:700;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.8rem;'>{a['dist']:.1f} miles away</div></div>", unsafe_allow_html=True)

    # --- REPORT ---
    st.markdown("<div id='section-6' class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True, hide_index=True)
        if st.button("Clear Report"): 
            st.session_state["session_recs"] = []
            st.rerun()
    else: st.info("No tracts selected.")