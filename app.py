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
    # --- 2. GLOBAL STYLING & TOC ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }

        /* Sidebar TOC */
        .toc-link { display: block; padding: 10px; color: #94a3b8 !important; text-decoration: none; font-weight: 600; font-size: 0.85rem; border-radius: 5px; margin-bottom: 5px; }
        .toc-link:hover { background-color: #1e293b; color: #4ade80 !important; }

        /* Filter Labels in White */
        label[data-testid="stWidgetLabel"] p { color: white !important; font-weight: 700 !important; font-size: 0.9rem !important; }

        /* Content Sections */
        .content-section { padding: 50px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; }
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 900px; margin-bottom: 30px; }
        
        /* Benefit Cards */
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 160px; }
        
        /* Dashboard Styling */
        .dashboard-card { background-color: #111827 !important; padding: 20px; border: 1px solid #1e293b; border-radius: 12px; height: 580px; overflow-y: auto; }
        .metric-card-inner { background-color: #1f2937; padding: 10px; border: 1px solid #374151; border-radius: 8px; text-align: center; margin-bottom: 8px; height: 85px; display: flex; flex-direction: column; justify-content: center; }
        .m-val { font-size: 1.0rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .m-lab { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        .anchor-ui-box { background: #1f2937; border: 1px solid #374151; padding: 12px; border-radius: 8px; margin-bottom: 8px; }
        </style>
        """, unsafe_allow_html=True)

    st.sidebar.title("Navigation")
    st.sidebar.markdown("""
        <a href="#section-1" class="toc-link">01. Portal Overview</a>
        <a href="#section-2" class="toc-link">02. Benefit Framework</a>
        <a href="#section-3" class="toc-link">03. Tract Advocacy</a>
        <a href="#section-4" class="toc-link">04. Best Practices</a>
        <a href="#section-5" class="toc-link">05. Strategic Analysis</a>
        <a href="#section-6" class="toc-link">06. Recommendation Report</a>
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

    def render_map_go(df):
        map_df = df.copy()
        map_df['Color_Category'] = map_df['Eligibility_Status'].apply(lambda x: 1 if x == 'Eligible' else 0)
        active = st.session_state.get("active_tract")
        center = {"lat": 30.9, "lon": -91.8}
        zoom = 6.5
        if active and active in tract_centers:
            center = {"lat": tract_centers[active][1], "lon": tract_centers[active][0]}
            zoom = 12.0

        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'],
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#cbd5e1'], [1, '#4ade80']], # Grey for Ineligible, Green for Eligible
            zmin=0, zmax=1, showscale=False,
            marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=zoom, center=center), # Light Grey Map Layer
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)',
            height=600, clickmode='event+select', uirevision="constant"
        )
        return fig

    # --- SECTIONS 1-4 (Same as previous) ---
    st.markdown("<div id='section-1'></div><div class='content-section'><div class='section-num'>SECTION 1</div><div class='section-title'>Louisiana OZ 2.0 Portal</div><div class='narrative-text'>Central intelligence hub for Louisiana's Opportunity Zones 2.0 initiative.</div></div>", unsafe_allow_html=True)
    st.markdown("<div id='section-2'></div><div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div><div class='narrative-text'>Federal tax incentives for long-term investment.</div>", unsafe_allow_html=True)
    c2 = st.columns(3)
    c2[0].markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Reinvest gains into a QOF until Dec 31, 2026.</p></div>", unsafe_allow_html=True)
    c2[1].markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Basis increase by 10% after 5 years.</p></div>", unsafe_allow_html=True)
    c2[2].markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Zero tax on appreciation after 10 years.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div id='section-3'></div><div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Tract Advocacy</div><div class='narrative-text'>Identifying 'Project Ready' tracts across Louisiana.</div>", unsafe_allow_html=True)
    c3 = st.columns(3)
    c3[0].markdown("<div class='benefit-card'><h3>Geographically Disbursed</h3><p>Ensuring rural parish participation.</p></div>", unsafe_allow_html=True)
    c3[1].markdown("<div class='benefit-card'><h3>Distressed Communities</h3><p>Prioritizing high poverty areas.</p></div>", unsafe_allow_html=True)
    c3[2].markdown("<div class='benefit-card'><h3>Project Ready</h3><p>Focusing on areas with immediate investment capacity.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div id='section-4'></div><div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><div class='narrative-text'>National expertise for state-level success.</div>", unsafe_allow_html=True)
    c4 = st.columns(3)
    c4[0].markdown("<div class='benefit-card'><h3>EIG</h3><p><a href='https://eig.org/ozs-guidance/' target='_blank'>View Guidance ↗</a></p></div>", unsafe_allow_html=True)
    c4[1].markdown("<div class='benefit-card'><h3>Frost Brown Todd</h3><p><a href='https://fbtgibbons.com/' target='_blank'>Visit Site ↗</a></p></div>", unsafe_allow_html=True)
    c4[2].markdown("<div class='benefit-card'><h3>America First Policy</h3><p><a href='https://americafirstpolicy.com/' target='_blank'>Learn More ↗</a></p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 5: STRATEGIC ANALYSIS ---
    st.markdown("<div id='section-5'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Analysis Command Center</div><div class='narrative-text'>Use this interface to perform deep-dive analysis into census tracts. Filter by region, parish, or specific GEOID to visualize anchor assets and socioeconomic profiles before adding a tract to your recommendation list.</div>", unsafe_allow_html=True)
    
    # Filter Row (White Labels)
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1: selected_region = st.selectbox("Select Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    with f2: selected_parish = st.selectbox("Select Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    with f3: 
        search_q = st.text_input("Search Census Tract Number", placeholder="Enter 11-digit GEOID")
        if search_q and search_q in master_df['geoid_str'].values:
            st.session_state["active_tract"] = search_q

    # The Map (Light Grey Layer)
    map_ev = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="main_map")
    if map_ev and "selection" in map_ev and map_ev["selection"]["points"]:
        st.session_state["active_tract"] = str(map_ev["selection"]["points"][0]["location"])
        st.rerun()

    # Analysis Row directly below map
    st.markdown("<br>", unsafe_allow_html=True)
    card_a, card_b, card_c = st.columns(3)
    curr_id = st.session_state["active_tract"]

    with card_a:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("📍 Anchor Assets")
        anc_f = st.selectbox("Filter Anchors", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()))
        if curr_id and curr_id in tract_centers:
            lon, lat = tract_centers[curr_id]
            wa = anchors_df.copy()
            if anc_f != "All Assets": wa = wa[wa['Type'] == anc_f]
            wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in wa.sort_values('dist').head(10).iterrows():
                st.markdown(f"<div class='anchor-ui-box'><b style='color:#4ade80;'>{a['Type']}</b><br>{a['Name']}<br><small>{a['dist']:.1f} miles away</small></div>", unsafe_allow_html=True)
        else: st.info("Select a tract to see nearby assets.")
        st.markdown("</div>", unsafe_allow_html=True)

    with card_b:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("📊 Tract Profile")
        if curr_id:
            row = master_df[master_df["geoid_str"] == curr_id].iloc[0]
            st.markdown(f"**GEOID:** `{curr_id}`")
            m_rows = [st.columns(3) for _ in range(3)]
            # Row 1
            m_rows[0][0].markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='m-lab'>Poverty</div></div>", unsafe_allow_html=True)
            m_rows[0][1].markdown(f"<div class='metric-card-inner'><div class='m-val'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='m-lab'>MFI</div></div>", unsafe_allow_html=True)
            m_rows[0][2].markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='m-lab'>Unemp.</div></div>", unsafe_allow_html=True)
            # Row 2
            m_rows[1][0].markdown(f"<div class='metric-card-inner'><div class='m-val'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='m-lab'>Metro</div></div>", unsafe_allow_html=True)
            m_rows[1][1].markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_int(row.get('Population 18 to 24', 0)):,}</div><div class='m-lab'>Pop 18-24</div></div>", unsafe_allow_html=True)
            m_rows[1][2].markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_int(row.get('Population 65 years and over', 0)):,}</div><div class='m-lab'>Pop 65+</div></div>", unsafe_allow_html=True)
            # Row 3
            m_rows[2][0].markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%</div><div class='m-lab'>Broadband</div></div>", unsafe_allow_html=True)
            m_rows[2][1].markdown(f"<div class='metric-card-inner'><div class='m-val'>{safe_int(row.get('Total Housing Units', 0)):,}</div><div class='m-lab'>Units</div></div>", unsafe_allow_html=True)
            m_rows[2][2].markdown(f"<div class='metric-card-inner'><div class='m-val'>{row.get('NMTC_Calculated', 'Ineligible')}</div><div class='m-lab'>NMTC</div></div>", unsafe_allow_html=True)
        else: st.info("Select a tract to view the 9-point socioeconomic profile.")
        st.markdown("</div>", unsafe_allow_html=True)

    with card_c:
        st.markdown("<div class='dashboard-card'>", unsafe_allow_html=True)
        st.subheader("✍️ Recommendation")
        cat = st.selectbox("Investment Category", ["Industrial", "Housing", "Retail", "Infrastructure", "Other"])
        ghost_text = "Proximity to anchors, NMTC status, or project readiness..."
        just = st.text_area("Justification", placeholder=ghost_text, height=250)
        if st.button("Save to Recommendation Report", use_container_width=True, type="primary"):
            if curr_id:
                st.session_state["session_recs"].append({"Tract": curr_id, "Category": cat, "Justification": just})
                st.toast("Saved!")
        st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 6: REPORT ---
    st.markdown("<div id='section-6'></div><div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True, hide_index=True)
        if st.button("Clear Report Data"):
            st.session_state["session_recs"] = []
            st.rerun()
    else: st.info("No recommendations added yet.")