import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

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

# --- 1. AUTHENTICATION (PROFESSIONAL DESIGN) ---
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
        st.markdown("""
            <style>
            .stApp { background-color: #0b0f19; }
            .login-card { background-color: #111827; padding: 40px; border-radius: 12px; border: 1px solid #1e293b; text-align: center; }
            </style>
        """, unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<div class='login-card'><h1 style='color:white; font-size:2rem; font-weight:900;'>OZ 2.0 PORTAL</h1><p style='color:#94a3b8;'>Strategic Investment Intelligence</p>", unsafe_allow_html=True)
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Sign In", on_click=password_entered, use_container_width=True)
            st.markdown("</div>", unsafe_allow_html=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; color: #f8fafc; }
        
        /* Best Practices Links */
        .benefit-card { background-color: #111827; padding: 25px; border: 1px solid #1e293b; border-radius: 8px; min-height: 180px; }
        .benefit-card h3 a { color: #4ade80; text-decoration: none; }
        
        /* Command Center Layout */
        .dashboard-card { background-color: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 12px; height: 650px; overflow-y: auto; }
        .metric-card-small { background: #1f2937; padding: 12px; border: 1px solid #374151; border-radius: 8px; text-align: center; margin-bottom: 10px; }
        .m-val { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .m-lab { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; }
        
        .anchor-item { background: #1f2937; border: 1px solid #374151; padding: 12px; border-radius: 8px; margin-bottom: 10px; }
        .view-site-btn { display: block; background-color: #4ade80; color: #0b0f19 !important; padding: 6px 0; border-radius: 4px; text-decoration: none !important; font-size: 0.7rem; font-weight: 900; text-align: center; margin-top: 8px; }
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

    def render_map(df):
        map_df = df.copy()
        recs = [r['Tract'] for r in st.session_state["session_recs"]]
        map_df['Color_Cat'] = map_df.apply(lambda r: 2 if r['geoid_str'] in recs else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Cat'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#d1d5db'], [0.5, '#4ade80'], [1, '#f97316']], # Grey, Green, Orange
            zmin=0, zmax=2, showscale=False, marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        fig.update_layout(
            mapbox=dict(style="light", zoom=6, center={"lat": 30.9, "lon": -91.8}),
            margin={"r":0,"t":0,"l":0,"b":0}, height=550, clickmode='event+select',
            uirevision=st.session_state.get("active_tract", "const")
        )
        return fig

    # --- NARRATIVE SECTIONS ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='section-title'>Louisiana OZ 2.0 Portal</div><p>Unlocking capital to fuel Louisiana's promising census tracts.</p></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div></div>", unsafe_allow_html=True)
    c2 = st.columns(3)
    c2[0].markdown("<div class='benefit-card'><h3>Gain Deferral</h3><p>Defer taxes until 2026.</p></div>", unsafe_allow_html=True)
    c2[1].markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>10% basis step-up after 5 years.</p></div>", unsafe_allow_html=True)
    c2[2].markdown("<div class='benefit-card'><h3>Exclusion</h3><p>Tax-free gains after 10 years.</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Advocacy</div><p>Targeting rural and distressed communities.</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div></div>", unsafe_allow_html=True)
    c4 = st.columns(3)
    c4[0].markdown("<div class='benefit-card'><h3><a href='https://eig.org/ozs-guidance/' target='_blank'>Economic Innovation Group ↗</a></h3><p>National OZ standard-setters.</p></div>", unsafe_allow_html=True)
    c4[1].markdown("<div class='benefit-card'><h3><a href='https://fbtgibbons.com/' target='_blank'>Frost Brown Todd ↗</a></h3><p>Legal & regulatory structuring.</p></div>", unsafe_allow_html=True)
    c4[2].markdown("<div class='benefit-card'><h3><a href='https://americafirstpolicy.com/' target='_blank'>America First Policy ↗</a></h3><p>Strategic state blueprints.</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: THE COMMAND CENTER ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping Tool</div>", unsafe_allow_html=True)
    
    # Filter Row
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1: region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered = master_df.copy()
    if region != "All Louisiana": filtered = filtered[filtered['Region'] == region]
    with f2: parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered['Parish'].dropna().unique().tolist()))
    if parish != "All in Region": filtered = filtered[filtered['Parish'] == parish]
    with f3: 
        search = st.text_input("Find Census Tract ID", placeholder="Search 11-Digit FIPS...")
        if search and search in master_df['geoid_str'].values:
            st.session_state["active_tract"] = search

    # Map Chart
    map_res = st.plotly_chart(render_map(filtered), use_container_width=True, on_select="rerun")
    if map_res and "selection" in map_res and map_res["selection"]["points"]:
        st.session_state["active_tract"] = str(map_res["selection"]["points"][0]["location"])
        st.rerun()

    # The Grid
    c1, c2, c3 = st.columns([0.25, 0.45, 0.3], gap="medium")
    curr_id = st.session_state["active_tract"]
    row = master_df[master_df["geoid_str"] == curr_id].iloc[0] if curr_id else None

    # Card 1: Anchors
    with c1:
        st.markdown("<div class='dashboard-card'><h3>📍 Anchor Assets</h3>", unsafe_allow_html=True)
        if curr_id and curr_id in tract_centers:
            lon, lat = tract_centers[curr_id]
            wa = anchors_df.copy()
            wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in wa.sort_values('dist').head(8).iterrows():
                link = f"<a href='{a['Link']}' target='_blank' class='view-site-btn'>VIEW SITE ↗</a>" if pd.notna(a.get('Link')) else ""
                st.markdown(f"<div class='anchor-item'><strong>{a['Name']}</strong><br><small>{a['Type']} • {a['dist']:.1f} mi</small>{link}</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Card 2: Tract Profile (The Perfect 9)
    with c2:
        st.markdown("<div class='dashboard-card'><h3>📊 Data Profile</h3>", unsafe_allow_html=True)
        if row is not None:
            st.write(f"**Tract {curr_id} ({row['Parish']})**")
            m_grid = st.columns(3)
            metrics = [
                ("Poverty Rate", f"{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%"),
                ("Median Income", f"${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}"),
                ("Unemployment", f"{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%"),
                ("Broadband Access", f"{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%"),
                ("Metro Status", row.get('Metro Status (Metropolitan/Rural)', 'N/A')),
                ("NMTC Status", "Eligible" if "Eligible" in str(row.get('NMTC_Calculated', '')) else "Ineligible"),
                ("Pop 18-24", f"{safe_int(row.get('Population 18 to 24', 0)):,}"),
                ("Pop 65+", f"{safe_int(row.get('Population 65 years and over', 0)):,}"),
                ("Total Pop", f"{safe_int(row.get('Total Population', 0)):,}")
            ]
            for i, (label, val) in enumerate(metrics):
                m_grid[i % 3].markdown(f"<div class='metric-card-small'><div class='m-val'>{val}</div><div class='m-lab'>{label}</div></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # Card 3: Justification (Dropdown inside)
    with c3:
        st.markdown("<div class='dashboard-card'><h3>✍️ Justification</h3>", unsafe_allow_html=True)
        cat = st.selectbox("Investment Focus", ["Industrial", "Housing", "Retail", "Mixed-Use", "Energy"])
        just = st.text_area("Strategic Narrative", height=240, placeholder="Highlight anchor proximity, data gaps, and readiness...")
        if st.button("Save to Report", use_container_width=True, type="primary"):
            if curr_id:
                st.session_state["session_recs"].append({"Tract": curr_id, "Category": cat, "Justification": just})
                st.toast("Tract Added!")
            else: st.error("Select a tract.")
        st.markdown("</div>", unsafe_allow_html=True)

    # Final Report
    if st.session_state["session_recs"]:
        st.divider()
        st.subheader("Selection Report")
        st.table(pd.DataFrame(st.session_state["session_recs"]))

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())