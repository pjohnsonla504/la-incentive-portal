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
        except: pass

    if not st.session_state["password_correct"]:
        st.markdown("<style>.stApp { background-color: #0b0f19; }</style>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<h2 style='text-align:center; color:white; font-family: sans-serif;'>OZ 2.0 Portal</h2>", unsafe_allow_html=True)
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        
        html, body, [class*="stApp"] { 
            font-family: 'Inter', sans-serif !important; 
            background-color: #0b0f19 !important; 
            color: #ffffff; 
        }

        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
        }
        div[data-baseweb="select"] * {
            color: #0f172a !important;
        }
        label[data-testid="stWidgetLabel"] { 
            color: #94a3b8 !important; 
            font-weight: 700 !important; 
            text-transform: uppercase; 
            font-size: 0.75rem !important; 
            letter-spacing: 0.05em;
        }

        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; }
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; margin-bottom: 25px; }
        
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 200px; transition: all 0.3s ease; }
        .benefit-card:hover { border-color: #4ade80 !important; }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 10px; font-weight: 800; }
        .benefit-card h3 a { color: #f8fafc; text-decoration: none; }
        .benefit-card h3 a:hover { color: #4ade80; }
        
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 90px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        
        div[data-testid="stTextArea"] textarea {
            background-color: #111827 !important;
            color: #f8fafc !important;
            border: 1px solid #1e293b !important;
            border-radius: 8px !important;
        }

        .anchor-card { background:#111827; border:1px solid #1e293b; padding:20px; border-radius:10px; margin-bottom:15px; }
        .anchor-type { color:#4ade80; font-size:0.7rem; font-weight:900; letter-spacing:0.12em; text-transform: uppercase; margin-bottom: 4px; }
        .anchor-name { color:#ffffff; font-weight:800; font-size:1.1rem; line-height: 1.2; margin-bottom:4px; }
        .anchor-dist { color:#94a3b8; font-size:0.85rem; margin-bottom: 12px; }
        
        .view-site-btn { 
            display: block; background-color: #4ade80; color: #0b0f19 !important; 
            padding: 8px 0; border-radius: 4px; text-decoration: none !important; 
            font-size: 0.75rem; font-weight: 900; text-align: center; border: 2px solid #4ade80; width: 100%;
        }
        .view-site-btn:hover { background-color: transparent; color: #4ade80 !important; }
        </style>
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
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
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

            if pov > 40 or mfi_pct <= 40 or unemp_ratio >= 2.5:
                return "Deep Distress"
            elif pov >= 20 or mfi_pct <= 80 or unemp_ratio >= 1.5:
                return "Eligible"
            return "Ineligible"

        master['NMTC_Calculated'] = master.apply(calc_nmtc_status, axis=1)
        
        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    coords = feature['geometry']['coordinates'][0]
                    if feature['geometry']['type'] == 'MultiPolygon': coords = coords[0]
                    pts = np.array(coords)
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def get_zoom_center(geoids):
        if not geoids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.0
        lats, lons = [], []
        found = False
        for feature in gj['features']:
            gid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
            if gid in geoids:
                found = True
                coords = feature['geometry']['coordinates'][0]
                if feature['geometry']['type'] == 'MultiPolygon': coords = coords[0]
                pts = np.array(coords)
                lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
        if not found: return {"lat": 30.9, "lon": -91.8}, 6.0
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        center = {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}
        max_diff = max(max_lat - min_lat, max_lon - min_lon)
        zoom = max(6, min(12, 8 - np.log2(max_diff))) if max_diff != 0 else 12
        return center, zoom

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        
        def get_color_cat(row):
            if row['geoid_str'] in selected_geoids: return 2
            return 1 if row['Eligibility_Status'] == 'Eligible' else 0
            
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        geoids = set(map_df['geoid_str'].tolist())
        center, zoom = get_zoom_center(geoids)
        
        sel_idx = []
        if st.session_state["active_tract"]:
            sel_idx = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist()
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'],
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], 
            zmin=0, zmax=2,
            showscale=False,
            marker=dict(opacity=0.7, line=dict(width=0.5, color='white')),
            selectedpoints=sel_idx,
            selected=dict(marker=dict(opacity=1.0)),
            unselected=dict(marker=dict(opacity=0.5)),
            hoverinfo="location"
        ))
        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)',
            height=600, clickmode='event+select', uirevision=str(center)
        )
        return fig

    # --- SECTIONS 1-4 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div style='color: #4ade80; font-weight: 700; text-transform: uppercase;'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div><div class='narrative-text'>Unlocking capital to fuel Louisiana's promising census tracts.</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div><div class='narrative-text'>Strategic federal tax incentives.</div>", unsafe_allow_html=True)
    c2cols = st.columns(3); c2cols[0].markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes for 5 years.</p></div>", unsafe_allow_html=True); c2cols[1].markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>10% basis step-up.</p></div>", unsafe_allow_html=True); c2cols[2].markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Zero gains tax after 10 years.</p></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Tract Advocacy</div><div class='narrative-text'>Identifying high readiness tracts.</div>", unsafe_allow_html=True)
    c3cols = st.columns(3); c3cols[0].markdown("<div class='benefit-card'><h3>Geographically Disbursed</h3><p>Rural focus.</p></div>", unsafe_allow_html=True); c3cols[1].markdown("<div class='benefit-card'><h3>Distressed Communities</h3><p>Federal definition.</p></div>", unsafe_allow_html=True); c3cols[2].markdown("<div class='benefit-card'><h3>Project Ready</h3><p>Likely to receive investment.</p></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><div class='narrative-text'>Leveraging national expertise.</div>", unsafe_allow_html=True)
    c4cols = st.columns(3); c4cols[0].markdown("<div class='benefit-card'><h3><a href='https://eig.org/ozs-guidance/' target='_blank'>Economic Innovation Group ↗</a></h3><p>OZ Guidance.</p></div>", unsafe_allow_html=True); c4cols[1].markdown("<div class='benefit-card'><h3><a href='https://fbtgibbons.com/' target='_blank'>Frost Brown Todd ↗</a></h3><p>Strategic Selection.</p></div>", unsafe_allow_html=True); c4cols[2].markdown("<div class='benefit-card'><h3><a href='https://americafirstpolicy.com/' target='_blank'>America First ↗</a></h3><p>State Blueprint.</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: STRATEGIC MAPPING & PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping & Profiling</div>", unsafe_allow_html=True)
    
    # Regional Filters
    f_col1, f_col2 = st.columns(2)
    with f_col1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    with f_col2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]

    # --- THE MAP (FULL WIDTH) ---
    combined_map = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="combined_map", config={'scrollZoom': True})
    if combined_map and "selection" in combined_map and combined_map["selection"]["points"]:
        new_id = str(combined_map["selection"]["points"][0]["location"])
        if st.session_state["active_tract"] != new_id:
            st.session_state["active_tract"] = new_id
            st.rerun()

    # --- DATA & ASSETS BELOW MAP ---
    st.markdown("<div style='margin-top: 25px;'></div>", unsafe_allow_html=True)
    
    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr].iloc[0]
        
        # Header Info Card
        pop_col = "Estimate!!Total!!Population for whom poverty status is determined"
        st.markdown(f"""
            <div style='display: flex; justify-content: space-between; align-items: center; background: #111827; padding: 20px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 20px;'>
                <div>
                    <div style='font-size: 1.8rem; font-weight: 900; color: #4ade80;'>{str(row['Parish']).upper()}</div>
                    <div style='color: #94a3b8; font-size: 0.85rem;'>GEOID: {curr}</div>
                </div>
                <div style='text-align: right;'>
                    <div style='font-size: 1.6rem; font-weight: 900; color: #f8fafc;'>{safe_int(row.get(pop_col, 0)):,}</div>
                    <div style='color: #94a3b8; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em;'>Population</div>