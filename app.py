
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
            button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(74, 222, 128, 0.3); }
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
                st.text_input("Username", key="username", placeholder="Enter your username")
                st.text_input("Password", type="password", key="password", placeholder="••••••••")
                st.button("Sign In", on_click=password_entered, use_container_width=True)
            st.markdown("<p style='text-align:center; color:#475569; font-size:0.8rem; margin-top:20px;'>Louisiana Opportunity Zones 2.0 | Admin Access Only</p>", unsafe_allow_html=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        div[data-baseweb="select"] > div { background-color: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 6px !important; }
        div[data-baseweb="select"] * { color: #0f172a !important; }
        label[data-testid="stWidgetLabel"] { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.05em; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; margin-bottom: 20px; line-height: 1.1; }
        .narrative-text { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; min-height: 280px; transition: all 0.3s ease; display: flex; flex-direction: column; }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 15px; font-weight: 800; font-size: 1.3rem; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; flex-grow: 1; }
        .benefit-card a { color: #4ade80; text-decoration: none; font-weight: 700; margin-top: 15px; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        .anchor-card { background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }
        .view-site-btn { display: block; background-color: #4ade80; color: #0b0f19 !important; padding: 6px 0; border-radius: 4px; text-decoration: none !important; font-size: 0.7rem; font-weight: 900; text-align: center; margin-top: 8px; border: 1px solid #4ade80; }
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
            if pov > 40 or mfi_pct <= 40 or unemp_ratio >= 2.5: return "Deep Distress"
            elif pov >= 20 or mfi_pct <= 80 or unemp_ratio >= 1.5: return "Eligible"
            return "Ineligible"

        master['NMTC_Calculated'] = master.apply(calc_nmtc_status, axis=1)
        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    if geom['type'] == 'Polygon':
                        pts = np.array(geom['coordinates'][0])
                    elif geom['type'] == 'MultiPolygon':
                        pts = np.array(geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def get_zoom_center(geoids):
        """Force recalculation of center and zoom."""
        if not geoids or not gj: 
            return {"lat": 30.9, "lon": -91.8}, 6.2
            
        lats, lons = [], []
        id_key = "GEOID" if "GEOID" in str(gj['features'][0]['properties']) else "GEOID20"
        
        for feature in gj['features']:
            gid = feature['properties'].get(id_key)
            if gid in geoids:
                geom = feature['geometry']
                if geom['type'] == 'Polygon':
                    coords = np.array(geom['coordinates'][0])
                elif geom['type'] == 'MultiPolygon':
                    # MultiPolygons are nested lists
                    coords = np.array(geom['coordinates'][0][0])
                else: continue
                lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
        
        if not lats: return {"lat": 30.9, "lon": -91.8}, 6.2
        
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        center = {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}
        
        # Range-based zoom logic
        lat_span = max_lat - min_lat
        lon_span = max_lon - min_lon
        max_span = max(lat_span, lon_span)
        
        if max_span <= 0: zoom = 12.5 # Single Point/Tract
        elif max_span < 0.1: zoom = 11.5
        elif max_span < 0.3: zoom = 10.0
        elif max_span < 0.8: zoom = 8.5
        elif max_span < 2.0: zoom = 7.5
        else: zoom = 6.2 # State view
            
        return center, zoom

    def render_map_go(df, filter_state_key):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        
        def get_color_cat(row):
            if row['geoid_str'] in selected_geoids: return 2
            return 1 if row['Eligibility_Status'] == 'Eligible' else 0
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        
        # If a tract is searched, zoom to it. Otherwise, zoom to the filtered parish/region bounds.
        if st.session_state.get("active_tract") and st.session_state["active_tract"] in map_df['geoid_str'].values:
            focus_geoids = {st.session_state["active_tract"]}
        else:
            focus_geoids = set(map_df['geoid_str'].tolist())
            
        center, zoom = get_zoom_center(focus_geoids)
        
        sel_idx = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist() if st.session_state["active_tract"] else []
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], zmin=0, zmax=2,
            showscale=False, marker=dict(opacity=0.7, line=dict(width=0.5, color='white')),
            selectedpoints=sel_idx, hoverinfo="location"
        ))
        
        fig.update_layout(
            mapbox=dict(
                style="carto-positron", 
                zoom=zoom, 
                center=center,
                scrollZoom=True # Explicitly ensure zoom scroll works
            ),
            margin={"r":0,"t":0,"l":0,"b":0}, 
            paper_bgcolor='rgba(0,0,0,0)',
            height=600, 
            clickmode='event+select',
            # uirevision changes whenever the filter state changes, forcing a camera update
            uirevision=filter_state_key 
        )
        return fig

    # --- SECTION 1-4: Narrative Content ---
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div><div class='narrative-text'>The Opportunity Zones Program provides federal tax incentives for reinvesting capital gains into designated low-income areas.</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Benefit Framework</div><div class='narrative-text'>Key incentives include Capital Gain Deferral, Basis Step-Up, and 10-Year Gain Exclusion.</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Tract Advocacy</div><div class='narrative-text'>Focusing on geographical diversity, market assessment, and anchor density.</div></div>""", unsafe_allow_html=True)
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>National Best Practices</div><div class='narrative-text'>Guided by EIG, Frost Brown Todd, and America First Policy Institute.</div></div>""", unsafe_allow_html=True)

    # --- SECTION 5: MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Opportunity Zone Mapping</div>", unsafe_allow_html=True)
    
    # 1. Filters
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana":
        filtered_df = filtered_df[filtered_df['Region'] == selected_region]
        
    with f_col2:
        selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    
    if selected_parish != "All in Region":
        filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
        
    with f_col3:
        # We need to filter the tract dropdown based on parish/region
        tract_opts = sorted(filtered_df['geoid_str'].tolist())
        selected_search = st.selectbox("Find Census Tract", ["Search Tract GEOID..."] + tract_opts)

    # State key to force map camera updates when filters change
    filter_key = f"{selected_region}-{selected_parish}-{selected_search}"

    if selected_search != "Search Tract GEOID...":
        if st.session_state["active_tract"] != selected_search:
            st.session_state["active_tract"] = selected_search
            st.rerun()

    # 2. Render Map
    combined_map = st.plotly_chart(
        render_map_go(filtered_df, filter_key), 
        use_container_width=True, 
        on_select="rerun", 
        key="combined_map"
    )
    
    # 3. Handle Selection
    if combined_map and "selection" in combined_map and combined_map["selection"]["points"]:
        new_id = str(combined_map["selection"]["points"][0]["location"])
        if st.session_state["active_tract"] != new_id:
            st.session_state["active_tract"] = new_id
            st.rerun()

    # 4. Detail Panel
    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        # Ensure row exists in master (it should)
        match = master_df[master_df["geoid_str"] == curr]
        if not match.empty:
            row = match.iloc[0]
            st.markdown(f"<div style='background: #111827; padding: 20px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 20px;'><div><div style='font-size: 1.8rem; font-weight: 900; color: #4ade80;'>{str(row['Parish']).upper()}</div><div style='color: #94a3b8;'>GEOID: {curr}</div></div></div>", unsafe_allow_html=True)
            
            d_col1, d_col2 = st.columns([0.6, 0.4], gap="large")
            with d_col1:
                st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem; letter-spacing:0.15em;'>TRACT DEMOGRAPHICS</p>", unsafe_allow_html=True)
                m_grid = st.columns(3)
                m_grid[0].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Status</div></div>", unsafe_allow_html=True)
                m_grid[1].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
                m_grid[2].markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>MFI</div></div>", unsafe_allow_html=True)
                
                justification = st.text_area("Strategic Justification", height=100, key="tract_justification")
                if st.button("Add to Recommendation Report", use_container_width=True, type="primary"):
                    st.session_state["session_recs"].append({"Tract": curr, "Justification": justification})
                    st.toast("Tract Added!"); st.rerun()
            with d_col2:
                st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem; letter-spacing:0.15em;'>NEARBY ANCHORS</p>", unsafe_allow_html=True)
                if curr in tract_centers:
                    lon, lat = tract_centers[curr]
                    working = anchors_df.copy()
                    working['dist'] = working.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                    list_html = ""
                    for _, a in working.sort_values('dist').head(8).iterrows():
                        list_html += f"<div class='anchor-card'><div style='color:#4ade80; font-size:0.7rem; font-weight:900;'>{str(a['Type'])}</div><div style='color:white; font-weight:800;'>{str(a['Name'])}</div><div style='color:#94a3b8; font-size:0.8rem;'>{a['dist']:.1f} miles</div></div>"
                    components.html(f"<style>body{{background:transparent; font-family:sans-serif; margin:0;}} .anchor-card{{background:#111827; border:1px solid #1e293b; padding:10px; border-radius:8px; margin-bottom:8px;}}</style>{list_html}", height=400, scrolling=True)

    # --- SECTION 6: REPORT ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        report_df = pd.DataFrame(st.session_state["session_recs"])
        st.dataframe(report_df, use_container_width=True, hide_index=True)
        if st.button("Clear Report"): st.session_state["session_recs"] = []; st.rerun()
    else: st.info("No tracts selected.")
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
