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
if "username" not in st.session_state:
    st.session_state["username"] = ""

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

# --- 1. PERSISTENCE ENGINE ---
def load_user_recs(username):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        recs_df = conn.read(worksheet="Recommendations", ttl=0) 
        if recs_df.empty: return []
        return recs_df[recs_df['username'] == username].to_dict('records')
    except: return []

def save_rec_to_cloud(rec_entry):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        rec_entry['username'] = st.session_state["username"]
        existing_df = conn.read(worksheet="Recommendations", ttl=0)
        new_row = pd.DataFrame([rec_entry])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True) if not existing_df.empty else new_row
        conn.update(worksheet="Recommendations", data=updated_df)
    except Exception as e:
        st.error(f"Cloud Save Failed: {e}")

# --- 2. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username_input"].strip()
            p = str(st.session_state["password_input"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = u
                    st.session_state["session_recs"] = load_user_recs(u)
                    return
            st.session_state["password_correct"] = False
            st.error("Invalid username or password")
        except Exception as e: st.error(f"Auth Error: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("<style>.stApp { background-color: #0b0f19 !important; }</style>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<h1 style='color: white; text-align:center;'>OZ 2.0 Portal</h1>", unsafe_allow_html=True)
            st.text_input("Username", key="username_input")
            st.text_input("Password", type="password", key="password_input")
            st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 3. GLOBAL STYLING & FROZEN NAV ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .nav-link:hover { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; margin-bottom: 20px; line-height: 1.1; }
        .narrative-text { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; min-height: 280px; display: flex; flex-direction: column; }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 15px; font-weight: 800; font-size: 1.3rem; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; }
        .anchor-card { background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }
        .view-site-btn { display: block; background-color: #4ade80; color: #0b0f19 !important; padding: 8px 0; border-radius: 4px; text-decoration: none !important; font-size: 0.75rem; font-weight: 900; text-align: center; margin-top: 10px; }
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

    # --- 4. DATA ENGINE ---
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
        def read_csv(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)
        master = read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1', 'true'] else 'Ineligible')
        
        def calc_nmtc(row):
            pov = safe_float(row.get("Estimate!!Percent below poverty level!!Population for whom poverty status is determined", 0))
            mfi = safe_float(row.get("Percentage of Benchmarked Median Family Income", 0))
            unemp = safe_float(row.get("Unemployment Ratio", 0))
            if pov > 40 or mfi <= 40 or unemp >= 2.5: return "Deep Distress"
            elif pov >= 20 or mfi <= 80 or unemp >= 1.5: return "Eligible"
            return "Ineligible"
        master['NMTC_Calculated'] = master.apply(calc_nmtc, axis=1)
        anchors = read_csv("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for f in gj['features']:
                gid = f['properties'].get('GEOID') or f['properties'].get('GEOID20')
                try:
                    geom = f['geometry']
                    pts = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
                    centers[gid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        sel_recs = [str(r['Tract']) for r in st.session_state["session_recs"]]
        map_df['Color_Category'] = map_df.apply(lambda r: 2 if str(r['geoid_str']) in sel_recs else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], zmin=0, zmax=2, showscale=False,
            marker=dict(opacity=0.6, line=dict(width=1, color='black'))
        ))
        fig.update_layout(mapbox=dict(style="carto-positron", zoom=6.5, center={"lat": 31.0, "lon": -91.8}), margin={"r":0,"t":0,"l":0,"b":0}, height=600)
        return fig

    # --- CONTENT SECTIONS 1-4 ---
    st.markdown("<div id='section-1' class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div><p class='narrative-text'>Drive long-term investments to low-income communities via the July 2025 OBBBA framework.</p></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-2' class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Benefit Framework</div>", unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1: st.markdown("<div class='benefit-card'><h3>Deferral</h3><p>Defer capital gains for 5 years.</p></div>", unsafe_allow_html=True)
    with b_col2: st.markdown("<div class='benefit-card'><h3>Step-Up</h3><p>Basis increase for long-term holds.</p></div>", unsafe_allow_html=True)
    with b_col3: st.markdown("<div class='benefit-card'><h3>Exclusion</h3><p>Zero tax on new gains after 10 years.</p></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-3' class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategy</div>", unsafe_allow_html=True)
    st.markdown("<div id='section-4' class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div>", unsafe_allow_html=True)

    # --- SECTION 5: MAPPING ---
    st.markdown("<div id='section-5' class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping</div></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    reg = c1.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered = master_df.copy()
    if reg != "All Louisiana": filtered = filtered[filtered['Region'] == reg]
    par = c2.selectbox("Parish", ["All in Region"] + sorted(filtered['Parish'].dropna().unique().tolist()))
    if par != "All in Region": filtered = filtered[filtered['Parish'] == par]
    tid = c3.selectbox("Find Tract", ["Search..."] + sorted(filtered['geoid_str'].tolist()))
    
    if tid != "Search...": st.session_state["active_tract"] = tid

    # Map Output
    map_selection = st.plotly_chart(render_map_go(filtered), use_container_width=True, on_select="rerun", key="main_map")
    if map_selection and "selection" in map_selection and map_selection["selection"]["points"]:
        st.session_state["active_tract"] = str(map_selection["selection"]["points"][0]["location"])

    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr].iloc[0]
        st.markdown(f"### {row['Parish'].upper()} | GEOID: {curr}")
        
        d_col1, d_col2 = st.columns([0.6, 0.4], gap="large")
        with d_col1:
            st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem;'>TRACT DEMOGRAPHICS</p>", unsafe_allow_html=True)
            r1 = st.columns(3)
            r1[0].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            r1[1].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['NMTC_Calculated'] != 'Ineligible' else 'NO'}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            r1[2].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['NMTC_Calculated'] == 'Deep Distress' else 'NO'}</div><div class='metric-label'>Deep Distress</div></div>", unsafe_allow_html=True)
            
            cat = st.selectbox("Category", ["Housing Development", "Business Development", "Technology & Research", "Healthcare & Community Services"])
            just = st.text_area("Strategic Justification")
            
            if st.button("Add to Recommendation Report", type="primary", use_container_width=True):
                new_entry = {
                    "username": st.session_state["username"],
                    "Tract": curr, 
                    "Parish": row['Parish'], 
                    "Category": cat, 
                    "Justification": just
                }
                save_rec_to_cloud(new_entry)
                st.session_state["session_recs"] = load_user_recs(st.session_state["username"])
                st.toast("Saved to Cloud!"); st.rerun()

        with d_col2:
            st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem;'>NEARBY ANCHORS</p>", unsafe_allow_html=True)
            if curr in tract_centers:
                lon, lat = tract_centers[curr]
                anch_data = anchors_df.copy()
                anch_data['dist'] = anch_data.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                for _, a in anch_data.sort_values('dist').head(4).iterrows():
                    st.markdown(f"<div class='anchor-card'><b>{a['Name']}</b><br>{a['dist']:.1f} mi - {a['Type']}</div>", unsafe_allow_html=True)

    # --- SECTION 6: REPORT ---
    st.markdown("<div id='section-6' class='content-section'><h2>Recommendation Report</h2></div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True)