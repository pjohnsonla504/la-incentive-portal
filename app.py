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

# Initialize Session States
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

        /* Sidebar Navigation Styling */
        [data-testid="stSidebar"] {
            background-color: #0f172a !important;
            border-right: 1px solid #1e293b;
        }

        .toc-link {
            display: block;
            padding: 10px;
            color: #94a3b8 !important;
            text-decoration: none;
            font-weight: 600;
            font-size: 0.9rem;
            border-radius: 5px;
            margin-bottom: 5px;
        }
        .toc-link:hover {
            background-color: #1e293b;
            color: #4ade80 !important;
        }

        /* Form Inputs */
        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
        }
        div[data-baseweb="select"] * { color: #0f172a !important; }
        
        /* Card Styling */
        .dashboard-card {
            background-color: #111827 !important;
            padding: 20px;
            border: 1px solid #1e293b;
            border-radius: 12px;
            height: 500px;
            overflow-y: auto;
        }
        .eligible-border {
            border: 2px solid #4ade80 !important;
        }
        
        .metric-card { 
            background-color: #1f2937 !important; 
            padding: 12px; 
            border: 1px solid #374151; 
            border-radius: 8px; 
            text-align: center;
            margin-bottom: 8px;
        }
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }

        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; }
        .hero-title { font-size: 3rem; font-weight: 900; margin-bottom: 15px; }
        .section-title { font-size: 2rem; font-weight: 900; margin-bottom: 20px; }
        
        /* Anchor Asset Cards */
        .anchor-card-ui { background:#1f2937; border:1px solid #374151; padding:12px; border-radius:8px; margin-bottom:10px; }
        .anchor-type-ui { color:#4ade80; font-size:0.6rem; font-weight:900; text-transform: uppercase; }
        .anchor-name-ui { color:#ffffff; font-weight:700; font-size:0.9rem; }
        </style>
        """, unsafe_allow_html=True)

    # Sidebar Table of Contents
    st.sidebar.title("Navigation")
    st.sidebar.markdown("""
        <a href="#section-1" class="toc-link">1. Portal Home</a>
        <a href="#section-2" class="toc-link">2. Benefit Framework</a>
        <a href="#section-3" class="toc-link">3. Tract Advocacy</a>
        <a href="#section-4" class="toc-link">4. Best Practices</a>
        <a href="#strategic-analysis" class="toc-link">5. Strategic Analysis Map</a>
        <a href="#report" class="toc-link">6. Recommendation Report</a>
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
        
        # Eligibility Rule: Green if YES, otherwise check OZ 1.0 status
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        # Assuming OZ 1.0 status is in a column (adjust name if different)
        master['OZ_1_Status'] = master['Opportunity Zone'].apply(lambda x: True if str(x).strip().lower() in ['yes', '1', 'oz'] else False)

        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    if geom['type'] == 'Polygon': coords = geom['coordinates'][0]
                    else: coords = geom['coordinates'][0][0]
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
                    pts = np.array(geometry['coordinates'][0])
                    lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
                elif geometry['type'] == 'MultiPolygon':
                    for poly in geometry['coordinates']:
                        pts = np.array(poly[0])
                        lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
        
        if not found: return {"lat": 30.9, "lon": -91.8}, 6.0
        center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
        zoom = 12.5 if active else 7.0
        return center, zoom

    def render_map_go(df):
        map_df = df.copy()
        
        # Color Logic: 0: Base, 1: OZ 1.0 (Blue), 2: OZ 2.0 (Green)
        def get_color_cat(row):
            if row['Eligibility_Status'] == 'Eligible': return 2
            if row.get('OZ_1_Status', False): return 1
            return 0
            
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        center, zoom = get_zoom_center(list(map_df['geoid_str']))
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'],
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#334155'], [0.5, '#3b82f6'], [1, '#4ade80']], # Grey -> Blue (OZ 1.0) -> Green (OZ 2.0)
            zmin=0, zmax=2,
            showscale=False,
            marker=dict(opacity=0.6, line=dict(width=0.5, color='white')),
            hoverinfo="location"
        ))
        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)',
            height=600, clickmode='event+select', uirevision="constant"
        )
        return fig

    # --- SECTIONS 1-4 (CONTEXT) ---
    st.markdown("<div id='section-1'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='hero-title'>Louisiana OZ 2.0 Portal</div><div style='color:#4ade80; font-weight:700;'>SECTION 1: INTRODUCTION</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-2'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-title'>Benefit Framework</div>", unsafe_allow_html=True)
    c2 = st.columns(3)
    c2[0].markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Until 2026.</p></div>", unsafe_allow_html=True)
    c2[1].markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Up to 10%.</p></div>", unsafe_allow_html=True)
    c2[2].markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>10 year hold.</p></div>", unsafe_allow_html=True)

    st.markdown("<div id='section-3'></div><div class='content-section'><div class='section-title'>Tract Advocacy</div></div>", unsafe_allow_html=True)
    st.markdown("<div id='section-4'></div><div class='content-section'><div class='section-title'>Best Practices</div></div>", unsafe_allow_html=True)

    # --- SECTION 5: THE COMMAND CENTER (CONSOLIDATED MAP & DATA) ---
    st.markdown("<div id='strategic-analysis'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-title'>Strategic Analysis Command Center</div>", unsafe_allow_html=True)
    
    # Filter Bar
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    
    with f2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    
    with f3: 
        search_query = st.text_input("Search by Census Tract Number", placeholder="Enter 11-digit GEOID...")
        if search_query:
            if search_query in master_df['geoid_str'].values:
                st.session_state["active_tract"] = search_query
            else:
                st.error("Tract not found.")

    # Main Map
    map_sub = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="main_map")
    if map_sub and "selection" in map_sub and map_sub["selection"]["points"]:
        st.session_state["active_tract"] = str(map_sub["selection"]["points"][0]["location"])
        st.rerun()

    # The 3-Card Footer Row
    st.markdown("---")
    col_a, col_b, col_c = st.columns(3)
    
    curr_id = st.session_state["active_tract"]
    is_eligible = False
    if curr_id:
        row_data = master_df[master_df["geoid_str"] == curr_id].iloc[0]
        is_eligible = row_data['Eligibility_Status'] == 'Eligible'

    # CARD 1: ANCHOR ASSETS
    with col_a:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("📍 Anchor Assets")
        asset_filter = st.selectbox("Filter Anchors", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()))
        
        if curr_id and curr_id in tract_centers:
            lon, lat = tract_centers[curr_id]
            working_anchors = anchors_df.copy()
            if asset_filter != "All Assets": working_anchors = working_anchors[working_anchors['Type'] == asset_filter]
            working_anchors['dist'] = working_anchors.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            
            for _, a in working_anchors.sort_values('dist').head(10).iterrows():
                st.markdown(f"""
                <div class='anchor-card-ui'>
                    <div class='anchor-type-ui'>{a['Type']}</div>
                    <div class='anchor-name-ui'>{a['Name']}</div>
                    <div style='color:#94a3b8; font-size:0.75rem;'>{a['dist']:.1f} miles away</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Select a tract to see nearby anchors.")
        st.markdown("</div>", unsafe_allow_html=True)

    # CARD 2: TRACT DATA PROFILE
    with col_b:
        border_class = "eligible-border" if is_eligible else ""
        st.markdown(f"<div class='dashboard-card {border_class}'>", unsafe_allow_html=True)
        st.subheader("📊 Tract Profile")
        if curr_id:
            st.markdown(f"**GEOID:** `{curr_id}`")
            if is_eligible: st.success("OZ 2.0 ELIGIBLE")
            
            m1, m2 = st.columns(2)
            m1.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row_data.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row_data.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
            
            m3, m4 = st.columns(2)
            m3.markdown(f"<div class='metric-card'><div class='metric-value'>{row_data.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            m4.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row_data.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
        else:
            st.info("Select a tract to view metrics.")
        st.markdown("</div>", unsafe_allow_html=True)

    # CARD 3: NARRATIVE JUSTIFICATION
    with col_c:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("✍️ Recommendation")
        cat_list = ["Industrial Expansion", "Affordable Housing", "Transit-Oriented Development", "Mixed-Use Retail", "Small Business Corridor"]
        selected_cat = st.selectbox("Investment Category", cat_list)
        
        ghost_msg = """How to justify: 
1. Link to nearest anchor assets.
2. Mention economic distress metrics.
3. Highlight project readiness."""

        just_text = st.text_area("Narrative Justification", 
                                placeholder=ghost_msg, 
                                height=150, 
                                max_chars=250,
                                key="narrative_input")
        
        if st.button("Add to Selection", use_container_width=True, type="primary"):
            if curr_id:
                st.session_state["session_recs"].append({
                    "Tract": curr_id,
                    "Category": selected_cat,
                    "Justification": just_text
                })
                st.toast(f"Tract {curr_id} added!")
            else:
                st.error("Select a tract first.")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 6: RECOMMENDATION REPORT ---
    st.markdown("<div id='report'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        rdf = pd.DataFrame(st.session_state["session_recs"])
        st.table(rdf)
        if st.button("Clear All"):
            st.session_state["session_recs"] = []
            st.rerun()
    else:
        st.info("Your report is currently empty.")