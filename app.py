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
from datetime import datetime

# --- 0. INITIAL CONFIG & STATE INITIALIZATION ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

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
        except Exception:
            st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
            .stApp { background-color: #0b0f19; }
            .login-card { max-width: 360px; margin: 140px auto 20px auto; padding: 30px; background: #111827; border: 1px solid #1e293b; border-top: 4px solid #4ade80; border-radius: 12px; text-align: center; }
            .login-title { font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 900; color: #ffffff; margin-bottom: 4px; }
            </style>
            <div class="login-card">
                <div class="login-title">OZ 2.0 Portal</div>
                <div style="color:#4ade80; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em;">Secure Stakeholder Access</div>
            </div>
        """, unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Sign In", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING (RESTORED INTER FONT) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; text-transform: uppercase; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; color: #f8fafc; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; line-height: 1.1; }
        .hero-subtitle { color: #4ade80; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 5px;}
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; margin-bottom: 25px; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 220px; transition: 0.3s; }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); background-color: #161b28 !important; }
        .benefit-card h3 { color: #f8fafc; font-size: 1.2rem; font-weight: 700; margin-bottom: 10px; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 5px; }
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; border: 1px solid #1e293b; margin-bottom: 15px; }
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
        geojson = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: geojson = json.load(f)
        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        poverty_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
        unemployment_col = 'Unemployment Rate (%)'
        mfi_col = 'Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)'
        
        def clean_numeric(s):
            try: return float(str(s).replace('%', '').replace('$', '').replace(',', '').strip())
            except: return 0.0

        master['_pov_num'] = master[poverty_col].apply(clean_numeric)
        master['_unemp_num'] = master[unemployment_col].apply(clean_numeric)
        master['_mfi_num'] = master[mfi_col].apply(clean_numeric)

        NAT_UNEMP, STATE_MFI = 5.3, 86934 
        master['NMTC_Eligible'] = ((master['_pov_num'] >= 20) | (master['_mfi_num'] <= (0.8 * STATE_MFI))).map({True:'Yes', False:'No'})
        master['Deeply_Distressed'] = ((master['_pov_num'] > 40) | (master['_mfi_num'] <= (0.4 * STATE_MFI))).map({True:'Yes', False:'No'})
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).lower() in ['eligible','yes','1'] else 'Ineligible')
        
        anchors = read_csv_safe("la_anchors.csv")
        centers = {}
        if geojson:
            for feature in geojson['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    coords = np.array(feature['geometry']['coordinates'][0]) if feature['geometry']['type'] == 'Polygon' else np.array(feature['geometry']['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map(df, is_filtered=False, height=600):
        center, zoom = {"lat": 30.8, "lon": -91.8}, 6.2
        if is_filtered and not df.empty:
            active_ids = df['geoid_str'].tolist()
            subset = [tract_centers[gid] for gid in active_ids if gid in tract_centers]
            if subset:
                lons, lats = zip(*subset)
                center, zoom = {"lat": np.mean(lats), "lon": np.mean(lons)}, 8.5
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", 
                                     color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#2d3748"},
                                     mapbox_style="carto-positron", zoom=zoom, center=center, opacity=0.5)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height)
        return fig

    # --- SECTION 1: HERO (RESTORED) ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div class='hero-subtitle'>Opportunity Zones 2.0</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div>
            <div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, and innovation in the communities that need it most.</div>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTION 2: BENEFIT FRAMEWORK (RESTORED) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>The OZ 2.0 framework is designed to bridge the gap between traditional investment and community development. By providing significant federal tax relief, the program incentivizes long-term equity investments.</div>", unsafe_allow_html=True)
    cols2 = st.columns(3)
    cards2 = [("Capital Gain Deferral", "Defer taxes on original capital gains for 5 years."),
              ("Basis Step-Up", "Qualified taxpayer receives 10% basis step-up (30% if rural)."),
              ("Permanent Exclusion", "Zero federal capital gains tax on appreciation after 10 years.")]
    for i, (ct, ctx) in enumerate(cards2):
        cols2[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 3: ADVOCACY (RESTORED) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Census Tract Advocacy</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>Effective advocacy requires a data-driven approach to selecting tracts that demonstrate both community need and investment potential.</div>", unsafe_allow_html=True)
    cols3 = st.columns(3)
    cards3 = [("Geographically Disbursed", "Zones Focused on rural and investment ready tracts."),
              ("Distressed Communities", "Eligibility is dependent on the federal definition of low-income."),
              ("Project Ready", "Aligning regional recommendations with tracts likely to receive investment.")]
    for i, (ct, ctx) in enumerate(cards3):
        cols3[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 4: BEST PRACTICES (RESTORED) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div>", unsafe_allow_html=True)
    cols4 = st.columns(3)
    cards4 = [("Economic Innovation Group", "Proximity to ports and manufacturing hubs.", "https://eig.org/ozs-guidance/"),
              ("Frost Brown Todd", "Utilizing local educational anchors for labor force.", "https://fbtgibbons.com/strategic-selection-of-opportunity-zones-2-0-a-governors-guide-to-best-practices/"),
              ("America First Policy", "Stack incentives to de-risk projects for long-term growth.", "https://www.americafirstpolicy.com/issues/from-policy-to-practice-opportunity-zones-2.0-reforms-and-a-state-blueprint-for-impact")]
    for i, (ct, ctx, url) in enumerate(cards4):
        cols4[i].markdown(f"<div class='benefit-card'><h3><a href='{url}' target='_blank' style='color:#4ade80; text-decoration:none;'>{ct}</a></h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAPPING (WITH FILTERS) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        sel_reg = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    with f_col2:
        p_df = master_df[master_df['Region'] == sel_reg] if sel_reg != "All Louisiana" else master_df
        sel_par = st.selectbox("Parish", ["All in Region"] + sorted(p_df['Parish'].dropna().unique().tolist()))
    with f_col3:
        sel_ast = st.selectbox("Anchor Type", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()))

    filtered_master = master_df.copy()
    is_filtering = False
    if sel_reg != "All Louisiana": 
        filtered_master = filtered_master[filtered_master['Region'] == sel_reg]
        is_filtering = True
    if sel_par != "All in Region": 
        filtered_master = filtered_master[filtered_master['Parish'] == sel_par]
        is_filtering = True

    c5a, c5b = st.columns([0.6, 0.4], gap="large")
    with c5a:
        st.plotly_chart(render_map(filtered_master, is_filtered=is_filtering), use_container_width=True, on_select="rerun", key="map5")
        if st.session_state.get("map5") and st.session_state["map5"]["selection"]["points"]:
            st.session_state["active_tract"] = str(st.session_state["map5"]["selection"]["points"][0]["location"])
    with c5b:
        # Asset list logic (same as before)
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        # [Asset list components.html logic here]

    # --- SECTION 6: PROFILING GRID (LINKED TO FILTERS) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.45, 0.55])
    with c6a:
        st.plotly_chart(render_map(filtered_master, is_filtered=is_filtering, height=750), use_container_width=True, on_select="rerun", key="map6")
        if st.session_state.get("map6") and st.session_state["map6"]["selection"]["points"]:
            st.session_state["active_tract"] = str(st.session_state["map6"]["selection"]["points"][0]["location"])
    with c6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<div class='tract-header-container'><div style='font-size:2rem; font-weight:900; color:#4ade80;'>{str(d.get('Parish','')).upper()}</div><div style='color:#94a3b8;'>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
            m_cols = [st.columns(3) for _ in range(3)]
            metrics = [(d.get('NMTC_Eligible'), "NMTC Eligible"), (d.get('Deeply_Distressed'), "Deeply Distressed"), (f"{d.get('_pov_num'):.1f}%", "Poverty Rate"),
                       (f"{d.get('_unemp_num'):.1f}%", "Unemployment"), (f"${d.get('_mfi_num'):,.0f}", "Median Income"), (d.get('Metro Status (Metropolitan/Rural)'), "Status")]
            for i, (val, lbl) in enumerate(metrics):
                m_cols[i//3][i%3].markdown(f"<div class='metric-card'><div class='metric-value'>{val}</div><div class='metric-label'>{lbl}</div></div>", unsafe_allow_html=True)

    # --- SECTION 7: EXPORT ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 7</div><div class='section-title'>My Recommendations</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        final_df = pd.DataFrame(st.session_state["session_recs"])
        st.dataframe(final_df, use_container_width=True, hide_index=True)
        st.download_button("Download CSV", data=final_df.to_csv(index=False).encode('utf-8'), file_name="OZ_Recs.csv", mime="text/csv")