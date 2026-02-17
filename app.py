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
    # --- 2. GLOBAL STYLING & SIDEBAR TOC ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        
        html, body, [class*="stApp"] { 
            font-family: 'Inter', sans-serif !important; 
            background-color: #0b0f19 !important; 
            color: #ffffff; 
        }

        /* Sidebar Navigation */
        [data-testid="stSidebar"] { background-color: #0f172a !important; border-right: 1px solid #1e293b; }
        .toc-link {
            display: block; padding: 10px; color: #94a3b8 !important;
            text-decoration: none; font-weight: 600; font-size: 0.85rem;
            border-radius: 5px; margin-bottom: 2px;
        }
        .toc-link:hover { background-color: #1e293b; color: #4ade80 !important; }

        /* Dashboard Components */
        .dashboard-card {
            background-color: #111827 !important;
            padding: 20px; border: 1px solid #1e293b;
            border-radius: 12px; height: 550px; overflow-y: auto;
        }
        .eligible-border { border: 2px solid #4ade80 !important; }
        
        .metric-card-inner { 
            background-color: #1f2937 !important; padding: 12px; 
            border: 1px solid #374151; border-radius: 8px; 
            text-align: center; margin-bottom: 8px;
        }
        .m-val { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .m-lab { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }

        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; }

        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 180px; }
        
        /* Anchor Cards */
        .anchor-ui { background:#1f2937; border:1px solid #374151; padding:12px; border-radius:8px; margin-bottom:10px; }
        .anchor-t { color:#4ade80; font-size:0.6rem; font-weight:900; text-transform: uppercase; }
        .anchor-n { color:#ffffff; font-weight:700; font-size:0.9rem; }
        </style>
        """, unsafe_allow_html=True)

    # Sidebar Table of Contents
    st.sidebar.title("Navigation")
    st.sidebar.markdown("""
        <a href="#section-1" class="toc-link">01. Portal Home</a>
        <a href="#section-2" class="toc-link">02. Benefit Framework</a>
        <a href="#section-3" class="toc-link">03. Tract Advocacy</a>
        <a href="#section-4" class="toc-link">04. Best Practices</a>
        <a href="#strategic-analysis" class="toc-link">05. Strategic Analysis Command Center</a>
        <a href="#report" class="toc-link">06. Recommendation Report</a>
    """, unsafe_allow_html=True)
    st.sidebar.divider()
    if st.sidebar.button("Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()

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
        
        # Eligibility Status for OZ 2.0
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )

        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
                    pts = np.array(coords)
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def get_zoom_center(geoids):
        active = st.session_state.get("active_tract")
        target_ids = [active] if active else geoids
        if not target_ids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.0
        
        lats, lons = [], []
        found = False
        for feature in gj['features']:
            gid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
            if gid in target_ids:
                found = True
                geometry = feature['geometry']
                if geometry['type'] == 'Polygon':
                    pts = np.array(geometry['coordinates'][0]); lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
                elif geometry['type'] == 'MultiPolygon':
                    for poly in geometry['coordinates']:
                        pts = np.array(poly[0]); lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
        
        if not found: return {"lat": 30.9, "lon": -91.8}, 6.0
        center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
        zoom = 12.0 if active else 7.0
        return center, zoom

    def render_map_go(df):
        map_df = df.copy()
        # Logic: 0: Base, 1: Eligible for OZ 2.0 (Green)
        map_df['Color_Category'] = map_df['Eligibility_Status'].apply(lambda x: 1 if x == 'Eligible' else 0)
        center, zoom = get_zoom_center(list(map_df['geoid_str']))
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'],
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#334155'], [1, '#4ade80']], 
            zmin=0, zmax=1, showscale=False,
            marker=dict(opacity=0.6, line=dict(width=0.5, color='white')),
            hoverinfo="location"
        ))
        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)',
            height=600, clickmode='event+select', uirevision="constant"
        )
        return fig

    # --- SECTIONS 1-4 ---
    st.markdown("<div id='section-1'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-2'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div>", unsafe_allow_html=True)
    c2 = st.columns(3)
    c2[0].markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Optimize tax liabilities via strategic reinvestment.</p></div>", unsafe_allow_html=True)
    c2[1].markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Enhance asset basis through long-term holding periods.</p></div>", unsafe_allow_html=True)
    c2[2].markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Eliminate capital gains tax on post-acquisition appreciation.</p></div>", unsafe_allow_html=True)

    st.markdown("<div id='section-3'></div><div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Tract Advocacy</div></div>", unsafe_allow_html=True)
    st.markdown("<div id='section-4'></div><div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div></div>", unsafe_allow_html=True)

    # --- SECTION 5: THE CONSOLIDATED COMMAND CENTER ---
    st.markdown("<div id='strategic-analysis'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Analysis Command Center</div>", unsafe_allow_html=True)
    
    # Filters Row
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    
    with f2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    
    with f3: 
        search_q = st.text_input("Search Census Tract Number", placeholder="Enter 11-digit GEOID...")
        if search_q and search_q in master_df['geoid_str'].values:
            st.session_state["active_tract"] = search_q

    # Unified Map
    map_ev = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="center_map")
    if map_ev and "selection" in map_ev and map_ev["selection"]["points"]:
        st.session_state["active_tract"] = str(map_ev["selection"]["points"][0]["location"])
        st.rerun()

    # The 3-Card Footer Row
    st.markdown("<br>", unsafe_allow_html=True)
    card_a, card_b, card_c = st.columns(3)
    
    curr_id = st.session_state["active_tract"]
    is_oz2 = False
    if curr_id:
        row_data = master_df[master_df["geoid_str"] == curr_id].iloc[0]
        is_oz2 = row_data['Eligibility_Status'] == 'Eligible'

    # CARD A: ANCHOR ASSETS
    with card_a:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("📍 Anchor Assets")
        anc_type = st.selectbox("Filter Anchors", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()), key="anc_filt")
        if curr_id and curr_id in tract_centers:
            lon, lat = tract_centers[curr_id]
            wa = anchors_df.copy()
            if anc_type != "All Assets": wa = wa[wa['Type'] == anc_type]
            wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in wa.sort_values('dist').head(8).iterrows():
                st.markdown(f"<div class='anchor-ui'><div class='anchor-t'>{a['Type']}</div><div class='anchor-n'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.75rem;'>{a['dist']:.1f} miles away</div></div>", unsafe_allow_html=True)
        else: st.info("Select a tract on the map to see nearby assets.")
        st.markdown("</div>", unsafe_allow_html=True)

    # CARD B: DATA PROFILE
    with card_b:
        b_style = "eligible-border" if is_oz2 else ""
        st.markdown(f"<div class='dashboard-card {b_style}'>", unsafe_allow_html=True)
        st.subheader("📊 Tract Profile")
        if curr_id:
            if is_oz2: st.success("OZ 2.0 ELIGIBLE")
            st.markdown(f"**Census Tract:** `{curr_id}`")
            m1, m2 = st.columns(2)
            m1.markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_float(row_data.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='m-lab'>Poverty Rate</div></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='metric-card-inner'><div class='m-val'>${safe_float(row_data.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='m-lab'>Median Income</div></div>", unsafe_allow_html=True)
            m3, m4 = st.columns(2)
            m3.markdown(f"<div class='metric-card-inner'><div class='m-val'>{row_data.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='m-lab'>Metro Status</div></div>", unsafe_allow_html=True)
            m4.markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_float(row_data.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='m-lab'>Unemployment</div></div>", unsafe_allow_html=True)
        else: st.info("Select a tract to view data.")
        st.markdown("</div>", unsafe_allow_html=True)

    # CARD C: JUSTIFICATION NARRATIVE
    with card_c:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("✍️ Recommendation")
        cat = st.selectbox("Category", ["Industrial", "Affordable Housing", "Retail Corridor", "Transit Hub", "Infrastructure"])
        ghost_msg = "How to justify:\n1. Connectivity to specific Anchors\n2. Mention high poverty/unemployment\n3. Note infrastructure readiness"
        just_text = st.text_area("Justification Narrative", placeholder=ghost_msg, max_chars=250, height=200)
        
        if st.button("Add to Report", use_container_width=True, type="primary"):
            if curr_id:
                st.session_state["session_recs"].append({"Tract": curr_id, "Category": cat, "Justification": just_text})
                st.toast(f"Tract {curr_id} added to report!")
            else: st.error("Please select a tract first.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 6: RECOMMENDATION REPORT ---
    st.markdown("<div id='report'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True, hide_index=True)
        if st.button("Clear Selection"):
            st.session_state["session_recs"] = []; st.rerun()
    else: st.info("Your recommendation list is empty.")