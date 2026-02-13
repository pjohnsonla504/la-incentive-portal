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
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
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
                    st.session_state["current_user"] = u 
                    return
            st.session_state["password_correct"] = False
        except Exception:
            st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;900&display=swap');
            .stApp { background-color: #0b0f19; }
            .login-card {
                max-width: 360px;
                margin: 140px auto 20px auto;
                padding: 30px;
                background: #111827;
                border: 1px solid #1e293b;
                border-top: 4px solid #4ade80;
                border-radius: 12px;
                text-align: center;
            }
            .login-title { font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 900; color: #ffffff; margin-bottom: 4px; }
            label, p, .stText { color: #ffffff !important; font-weight: 600 !important; }
            div[data-baseweb="input"] { background-color: #f8fafc !important; border-radius: 6px !important; }
            input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-family: 'Inter', sans-serif !important; }
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
    conn = st.connection("gsheets", type=GSheetsConnection)

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        label[data-testid="stWidgetLabel"] p { color: #ffffff !important; font-size: 0.95rem !important; font-weight: 700 !important; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; line-height: 1.1; }
        .hero-subtitle { color: #4ade80; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 5px;}
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; margin-bottom: 25px; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 220px; transition: all 0.3s ease; }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); background-color: #161b28 !important; }
        .benefit-card h3 { color: #f8fafc; font-size: 1.2rem; font-weight: 700; margin-bottom: 10px; }
        .benefit-card a { color: #4ade80; text-decoration: none; }
        .benefit-card a:hover { text-decoration: underline; color: #ffffff; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 12px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 5px; line-height: 1.2;}
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; margin-bottom: 15px; border: 1px solid #1e293b; }
        .stSelectbox div[data-baseweb="select"], .stTextArea textarea { background-color: #111827 !important; color: #ffffff !important; border: 1px solid #1e293b !important; }
        [data-testid="stDataFrame"] { background-color: #111827; border-radius: 8px; border: 1px solid #1e293b; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE (INTEGRATED POLICYMAP DISTRESS LOGIC) ---
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
        
        def clean_num(s):
            try: return float(str(s).replace('%','').replace('$','').replace(',','').strip())
            except: return 0.0

        master['_pov'] = master[poverty_col].apply(clean_num)
        master['_unemp'] = master[unemployment_col].apply(clean_num)
        master['_mfi'] = master[mfi_col].apply(clean_num)

        NAT_UNEMP = 5.3 
        STATE_MFI = 86934 

        # NMTC ELIGIBLE (Standard LIC)
        master['NMTC_Eligible'] = ((master['_pov'] >= 20) | (master['_mfi'] <= (0.8 * STATE_MFI))).map({True:'Yes', False:'No'})
        # SEVERE DISTRESS (PolicyMap maroon/brown - 30% Poverty or 60% MFI)
        master['Severe_Distress'] = ((master['_pov'] >= 30) | (master['_mfi'] <= (0.6 * STATE_MFI)) | (master['_unemp'] >= (1.5 * NAT_UNEMP))).map({True:'Yes', False:'No'})
        # DEEP DISTRESS (PolicyMap red - 40% Poverty or 40% MFI)
        master['Deep_Distress'] = ((master['_pov'] >= 40) | (master['_mfi'] <= (0.4 * STATE_MFI)) | (master['_unemp'] >= (2.5 * NAT_UNEMP))).map({True:'Yes', False:'No'})

        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).lower() in ['eligible','yes','1'] else 'Ineligible')
        
        anchors = read_csv_safe("la_anchors.csv")
        anchors['Link'] = anchors.get('Link', pd.Series([""]*len(anchors))).fillna("")
        
        centers = {}
        if geojson:
            for f in geojson['features']:
                gid = f['properties'].get('GEOID') or f['properties'].get('GEOID20')
                try:
                    c = np.array(f['geometry']['coordinates'][0]) if f['geometry']['type'] == 'Polygon' else np.array(f['geometry']['coordinates'][0][0])
                    centers[gid] = [np.mean(c[:, 0]), np.mean(c[:, 1])]
                except: pass
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map(df, is_filtered=False, height=600):
        center = {"lat": 30.8, "lon": -91.8}
        zoom = 6.2 
        if is_filtered and not df.empty:
            active_ids = df['geoid_str'].tolist()
            subset_centers = [tract_centers[gid] for gid in active_ids if gid in tract_centers]
            if subset_centers:
                lons, lats = zip(*subset_centers)
                center = {"lat": np.mean(lats), "lon": np.mean(lons)}
                zoom = 8.5 
        
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", 
                                     color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="carto-positron", zoom=zoom, center=center, opacity=0.5)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height, clickmode='event+select')
        return fig

    # --- SECTION 1: HERO ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div class='hero-subtitle'>Opportunity Zones 2.0</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div>
            <div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, and innovation in the communities that need it most.</div>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTION 2: BENEFIT FRAMEWORK ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>The OZ 2.0 framework is designed to bridge the gap between traditional investment and community development. By providing significant federal tax relief, the program incentivizes long-term equity investments in designated census tracts.</div>", unsafe_allow_html=True)
    cols2 = st.columns(3)
    cards2 = [
        ("Capital Gain Deferral", "Defer taxes on original capital gains for 5 years."),
        ("Basis Step-Up", "Qualified taxpayer receives 10% basis step-up (30% if rural)."),
        ("Permanent Exclusion", "Zero federal capital gains tax on appreciation after 10 years.")
    ]
    for i, (ct, ctx) in enumerate(cards2):
        cols2[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 3: CENSUS TRACT ADVOCACY ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Census Tract Advocacy</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>Effective advocacy requires a data-driven approach to selecting tracts that demonstrate both high community need and strong investment potential.</div>", unsafe_allow_html=True)
    cols3 = st.columns(3)
    cards3 = [
        ("Geographically Disbursed", "Zones Focused on rural and investment ready tracts."),
        ("Distressed Communities", "Eligibility is dependent on the federal definition of a low-income community."),
        ("Project Ready", "Aligning regional recommendations with tracts likely to receive private investment.")
    ]
    for i, (ct, ctx) in enumerate(cards3):
        cols3[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 4: BEST PRACTICES ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>Successful Opportunity Zone projects leverage institutional knowledge and local assets to minimize risk for private investors.</div>", unsafe_allow_html=True)
    cols4 = st.columns(3)
    cards4 = [
        ("Economic Innovation Group", "Proximity to ports and manufacturing hubs ensures long-term tenant demand.", "https://eig.org/ozs-guidance/"),
        ("Frost Brown Todd", "Utilizing local educational anchors to provide a skilled labor force.", "https://fbtgibbons.com/strategic-selection-of-opportunity-zones-2-0-a-governors-guide-to-best-practices/"),
        ("America First Policy Institute", "Stack incentives to de-risk projects for long-term growth.", "https://www.americafirstpolicy.com/issues/from-policy-to-practice-opportunity-zones-2.0-reforms-and-a-state-blueprint-for-impact")
    ]
    for i, (ct, ctx, url) in enumerate(cards4):
        cols4[i].markdown(f"<div class='benefit-card'><h3><a href='{url}' target='_blank'>{ct}</a></h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    
    # Regional Selectors
    unique_regions = sorted(master_df['Region'].dropna().unique().tolist())
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        selected_region = st.selectbox("Filter by Region", ["All Louisiana"] + unique_regions)
    with f_col2:
        available_parishes = sorted(master_df[master_df['Region'] == selected_region]['Parish'].dropna().unique().tolist()) if selected_region != "All Louisiana" else sorted(master_df['Parish'].dropna().unique().tolist())
        selected_parish = st.selectbox("Filter by Parish", ["All in Region"] + available_parishes)
    with f_col3:
        asset_types = sorted(anchors_df['Type'].unique().tolist())
        selected_asset_type = st.selectbox("Filter by Anchor Asset Type", ["All Assets"] + asset_types)

    filtered_df = master_df.copy()
    is_actively_filtering = False
    if selected_region != "All Louisiana":
        filtered_df = filtered_df[filtered_df['Region'] == selected_region]
        is_actively_filtering = True
    if selected_parish != "All in Region":
        filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
        is_actively_filtering = True

    c5a, c5b = st.columns([0.6, 0.4], gap="large")
    with c5a:
        f5 = render_map(filtered_df, is_filtered=is_actively_filtering)
        s5 = st.plotly_chart(f5, use_container_width=True, on_select="rerun", key="map5")
        if s5 and s5["selection"]["points"]:
            st.session_state["active_tract"] = str(s5["selection"]["points"][0]["location"])
    
    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        list_html = ""
        if curr in tract_centers:
            lon, lat = tract_centers[curr]
            working_anchors = anchors_df.copy()
            if selected_asset_type != "All Assets":
                working_anchors = working_anchors[working_anchors['Type'] == selected_asset_type]
            working_anchors['dist'] = working_anchors.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in working_anchors.sort_values('dist').head(12).iterrows():
                link_btn = f"<div style='margin-top:10px;'><a href='{a['Link']}' target='_blank' style='display:inline-block; background:#4ade80; color:#0b0f19; padding:5px 12px; border-radius:4px; font-size:0.7rem; font-weight:900; text-decoration:none;'>VIEW SITE 🔗</a></div>" if a['Type'] in ['Land','Buildings'] and str(a['Link']).strip() else ""
                list_html += f"<div style='background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px;'><div style='color:#4ade80; font-size:0.65rem; font-weight:900;'>{str(a['Type']).upper()}</div><div style='color:#ffffff; font-weight:700; font-size:1rem; margin: 4px 0;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.75rem;'>📍 {a['dist']:.1f} miles away</div>{link_btn}</div>"
        components.html(f"<div style='height: 530px; overflow-y: auto; font-family: sans-serif;'>{list_html}</div>", height=550)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Metrics</div>", unsafe_allow_html=True)
    row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
    if not row.empty:
        d = row.iloc[0]
        st.markdown(f"<div class='tract-header-container'><div style='font-size:2rem; font-weight:900; color:#4ade80;'>{str(d.get('Parish','')).upper()}</div><div style='color:#94a3b8;'>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
        m_cols = st.columns(4)
        metrics = [
            (d['NMTC_Eligible'], "NMTC Eligible"),
            (d['Severe_Distress'], "Severe Distress"),
            (d['Deep_Distress'], "Deep Distress"),
            (f"{d['_pov']:.1f}%", "Poverty Rate"),
            (f"{d['_unemp']:.1f}%", "Unemployment Rate"),
            (f"${d['_mfi']:,.0f}", "Median Income"),
            (d.get('Broadband Internet (%)','0%'), "Broadband %"),
            (d.get('Metro Status (Metropolitan/Rural)','N/A'), "Status")
        ]
        for i, (val, lbl) in enumerate(metrics):
            m_cols[i % 4].markdown(f"<div class='metric-card'><div class='metric-value'>{val}</div><div class='metric-label'>{lbl}</div></div>", unsafe_allow_html=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())