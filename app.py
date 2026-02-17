import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana OZ 2.0 Command Center", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
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

def read_csv_with_fallback(path):
    for enc in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
        try: return pd.read_csv(path, encoding=enc)
        except: continue
    return pd.read_csv(path)

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
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        
        .content-section { padding: 30px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2rem; font-weight: 900; margin-bottom: 15px; color: #f8fafc; }
        
        .dashboard-card { 
            background-color: #111827; padding: 20px; border: 1px solid #1e293b; 
            border-radius: 12px; height: 620px; overflow-y: auto; 
        }
        
        .metric-card-small { 
            background: #1f2937; padding: 10px; border: 1px solid #374151; 
            border-radius: 8px; text-align: center; margin-bottom: 8px;
        }
        .m-val-small { font-size: 0.95rem; font-weight: 900; color: #4ade80; }
        .m-lab-small { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; }
        
        .view-site-btn { 
            display: block; background-color: #4ade80; color: #0b0f19 !important; 
            padding: 5px 0; border-radius: 4px; text-decoration: none !important; 
            font-size: 0.7rem; font-weight: 900; text-align: center; margin-top: 8px; 
        }
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
        
        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )

        anchors = read_csv_with_fallback("la_anchors.csv")
        
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
        if not target_ids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.5
        lats, lons = [], []
        for feature in gj['features']:
            gid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
            if gid in target_ids:
                geom = feature['geometry']
                coords = geom['coordinates'] if geom['type'] == 'Polygon' else geom['coordinates'][0]
                for poly in coords:
                    pts = np.array(poly)
                    if pts.ndim == 2:
                        lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
        if not lats: return {"lat": 30.9, "lon": -91.8}, 6.5
        center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
        zoom = 12 if active else 7
        return center, zoom

    def render_map(df):
        map_df = df.copy()
        recs = [r['Tract'] for r in st.session_state["session_recs"]]
        # 0: Ineligible (Grey), 1: Eligible (Green), 2: Selected (Orange)
        map_df['Color_Cat'] = map_df.apply(lambda r: 2 if r['geoid_str'] in recs else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        center, zoom = get_zoom_center(map_df['geoid_str'].tolist())
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Cat'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#d1d5db'], [0.5, '#4ade80'], [1, '#f97316']], 
            zmin=0, zmax=2, showscale=False, marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        fig.update_layout(
            mapbox=dict(style="light", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, height=500, clickmode='event+select',
            uirevision=st.session_state.get("active_tract", "const")
        )
        return fig

    # --- 4. NAVIGATION ---
    with st.sidebar:
        st.markdown("### Table of Contents")
        nav = st.radio("Go to Section:", ["Full Dashboard", "Introduction", "Benefit Framework", "Strategic Advocacy", "Best Practices", "Strategic Mapping Tool"])
        st.divider()
        if st.button("Reset Selection"):
            st.session_state["active_tract"] = None
            st.rerun()

    # --- 5. NARRATIVE CONTENT ---
    def show_intro():
        st.markdown("<div class='content-section' id='intro'><div class='section-num'>SECTION 1</div><div class='section-title'>Louisiana OZ 2.0 Portal</div><p>Unlocking capital to fuel Louisiana's promising census tracts. This portal identifies high-readiness areas for the next phase of Opportunity Zone investment.</p></div>", unsafe_allow_html=True)

    def show_benefits():
        st.markdown("<div class='content-section' id='benefits'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div></div>", unsafe_allow_html=True)
        cols = st.columns(3)
        with cols[0]: st.info("**Gain Deferral**\nDefer taxes until 2026.")
        with cols[1]: st.info("**Basis Step-Up**\n10% increase after 5 years.")
        with cols[2]: st.info("**Permanent Exclusion**\nTax-free gains after 10 years.")

    def show_advocacy():
        st.markdown("<div class='content-section' id='advocacy'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Advocacy</div><p>Focusing on rural and deeply distressed communities with high impact potential.</p></div>", unsafe_allow_html=True)

    def show_practices():
        st.markdown("<div class='content-section' id='practices'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><p>Leveraging proven national blueprint strategies for local implementation.</p></div>", unsafe_allow_html=True)

    # --- 6. MAPPING TOOL (COMMAND CENTER) ---
    def show_mapping_tool():
        st.markdown("<div class='section-num' style='margin-top:30px;'>SECTION 5</div><div class='section-title'>Strategic Mapping Tool</div>", unsafe_allow_html=True)
        
        # Filters
        f1, f2, f3 = st.columns([1, 1, 1])
        with f1: region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
        filtered = master_df.copy()
        if region != "All Louisiana": filtered = filtered[filtered['Region'] == region]
        with f2: parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered['Parish'].dropna().unique().tolist()))
        if parish != "All in Region": filtered = filtered[filtered['Parish'] == parish]
        with f3: 
            search = st.text_input("Search 11-Digit FIPS", placeholder="Enter Tract ID...")
            if search and search in master_df['geoid_str'].values:
                st.session_state["active_tract"] = search

        # Map Display
        map_res = st.plotly_chart(render_map(filtered), use_container_width=True, on_select="rerun")
        if map_res and "selection" in map_res and map_res["selection"]["points"]:
            st.session_state["active_tract"] = str(map_res["selection"]["points"][0]["location"])
            st.rerun()

        # 3-Card Grid
        c1, c2, c3 = st.columns([0.25, 0.45, 0.3], gap="medium")
        curr_id = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr_id].iloc[0] if curr_id else None

        # Cell 1: Anchors
        with c1:
            st.markdown("<div class='dashboard-card'><h3>📍 Anchors</h3>", unsafe_allow_html=True)
            if curr_id and curr_id in tract_centers:
                lon, lat = tract_centers[curr_id]
                wa = anchors_df.copy()
                wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                for _, a in wa.sort_values('dist').head(8).iterrows():
                    link = f"<a href='{a['Link']}' target='_blank' class='view-site-btn'>VIEW SITE ↗</a>" if pd.notna(a.get('Link')) else ""
                    st.markdown(f"<div style='background:#1f2937; padding:10px; border-radius:8px; margin-bottom:8px;'><strong>{a['Name']}</strong><br><small>{a['Type']} • {a['dist']:.1f} mi</small>{link}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Cell 2: Data Profile (9 Cards)
        with c2:
            st.markdown("<div class='dashboard-card'><h3>📊 Data Profile</h3>", unsafe_allow_html=True)
            if row is not None:
                st.write(f"**Tract {curr_id} ({row['Parish']})**")
                m_grid = st.columns(3)
                metrics = [
                    ("Poverty Rate", f"{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%"),
                    ("Median Income", f"${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}"),
                    ("Unemployment", f"{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%"),
                    ("Broadband", f"{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%"),
                    ("Metro Status", row.get('Metro Status (Metropolitan/Rural)', 'N/A')),
                    ("NMTC Status", "Eligible" if "Eligible" in str(row.get('NMTC_Calculated', '')) else "Ineligible"),
                    ("Pop 18-24", f"{safe_int(row.get('Population 18 to 24', 0)):,}"),
                    ("Pop 65+", f"{safe_int(row.get('Population 65 years and over', 0)):,}"),
                    ("Total Pop", f"{safe_int(row.get('Total Population', 0)):,}")
                ]
                for i, (label, val) in enumerate(metrics):
                    m_grid[i % 3].markdown(f"<div class='metric-card-small'><div class='m-val-small'>{val}</div><div class='m-lab-small'>{label}</div></div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Cell 3: Justification
        with c3:
            st.markdown("<div class='dashboard-card'><h3>✍️ Justification</h3>", unsafe_allow_html=True)
            cat = st.selectbox("Investment Focus", ["Industrial", "Housing", "Retail", "Energy", "Infrastructure"])
            just = st.text_area("Narrative Justification", height=250, placeholder="INSTRUCTIONS:\n- Highlight proximity to anchors in Cell 1.\n- Reference the 9 metrics in Cell 2.\n- Describe project readiness and community impact.")
            if st.button("Add to Selection Report", use_container_width=True, type="primary"):
                if curr_id:
                    st.session_state["session_recs"].append({"Tract": curr_id, "Category": cat, "Justification": just})
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

    # --- 7. MAIN RENDER LOGIC ---
    if nav == "Full Dashboard":
        show_intro()
        show_benefits()
        show_advocacy()
        show_practices()
        show_mapping_tool()
    elif nav == "Introduction": show_intro()
    elif nav == "Benefit Framework": show_benefits()
    elif nav == "Strategic Advocacy": show_advocacy()
    elif nav == "Best Practices": show_practices()
    elif nav == "Strategic Mapping Tool": show_mapping_tool()

    # Final Report Table
    if st.session_state["session_recs"]:
        st.divider()
        st.subheader("Selection Summary")
        st.table(pd.DataFrame(st.session_state["session_recs"]))