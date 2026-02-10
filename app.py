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

# Persistent storage for the current session's recommendations
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
        except Exception as e:
            st.error(f"Auth Error: {e}")

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
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; line-height: 1.1; }
        .hero-subtitle { color: #4ade80; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 5px;}
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; margin-bottom: 25px; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 220px; transition: all 0.3s ease; }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); background-color: #161b28 !important; }
        .benefit-card h3 { color: #f8fafc; font-size: 1.2rem; font-weight: 700; margin-bottom: 10px; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 12px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 5px; line-height: 1.2;}
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; margin-bottom: 15px; border: 1px solid #1e293b; }
        
        label[data-testid="stWidgetLabel"] p { color: #ffffff !important; font-size: 0.9rem !important; font-weight: 700 !important; }
        .stSelectbox div[data-baseweb="select"], .stTextArea textarea { background-color: #111827 !important; color: #ffffff !important; border: 1px solid #1e293b !important; }
        [data-testid="stDataFrame"] { background-color: #111827; border-radius: 8px; border: 1px solid #1e293b; }
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
            if pd.isna(s): return 0.0
            s = str(s).replace('%', '').replace('$', '').replace(',', '').strip()
            try: return float(s)
            except: return 0.0

        master['_pov_num'] = master[poverty_col].apply(clean_numeric)
        master['_unemp_num'] = master[unemployment_col].apply(clean_numeric)
        master['_mfi_num'] = master[mfi_col].apply(clean_numeric)

        NAT_UNEMP = 5.3
        STATE_MFI = 86934 

        master['NMTC_Eligible'] = (
            (master['_pov_num'] >= 20) | 
            (master['_mfi_num'] <= (0.8 * STATE_MFI)) | 
            (master['_unemp_num'] >= (1.5 * NAT_UNEMP))
        ).map({True: 'Yes', False: 'No'})

        master['Deeply_Distressed'] = (
            (master['_pov_num'] > 40) | 
            (master['_mfi_num'] <= (0.4 * STATE_MFI)) | 
            (master['_unemp_num'] >= (2.5 * NAT_UNEMP))
        ).map({True: 'Yes', False: 'No'})

        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
        # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        
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

    def render_map(df, height=600):
        center = {"lat": 30.8, "lon": -91.8}
        zoom = 6.2
        if not df.empty and df['geoid_str'].nunique() < 200:
            active_ids = df['geoid_str'].tolist()
            subset_centers = [tract_centers[gid] for gid in active_ids if gid in tract_centers]
            if subset_centers:
                lons, lats = zip(*subset_centers)
                center = {"lat": np.mean(lats), "lon": np.mean(lons)}
                zoom = 9.5
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", 
                                     color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#cbd5e1"},
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
    st.markdown("<div class='narrative-text'>The OZ 2.0 framework is designed to bridge the gap between traditional investment and community development. By providing significant federal tax relief, the program incentivizes long-term equity investments in designated census tracts, ensuring that capital remains active within the Louisiana economy for a minimum of ten years.</div>", unsafe_allow_html=True)
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
    st.markdown("<div class='narrative-text'>Effective advocacy requires a data-driven approach to selecting tracts that demonstrate both high community need and strong investment potential. By focusing on rural and deeply distressed areas, we can ensure that the Opportunity Zone benefits are distributed equitably across all of Louisiana's diverse economic landscapes.</div>", unsafe_allow_html=True)
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
    st.markdown("<div class='narrative-text'>Successful Opportunity Zone projects leverage institutional knowledge and local assets to minimize risk for private investors. These best practices represent a synthesis of national policy research and localized economic development strategies tailored for the Louisiana market.</div>", unsafe_allow_html=True)
    cols4 = st.columns(3)
    cards4 = [
        ("Economic Innovation Group", "Proximity to ports and manufacturing hubs ensures long-term tenant demand."),
        ("Frost Brown Todd", "Utilizing local educational anchors to provide a skilled labor force."),
        ("American Policy Institute", "Stack incentives to de-risk projects for long-term growth.")
    ]
    for i, (ct, ctx) in enumerate(cards4):
        cols4[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- GLOBAL PARISH FILTER ---
    st.markdown("<br>", unsafe_allow_html=True)
    all_parishes = sorted(master_df['Parish'].dropna().unique().tolist())
    selected_parish = st.selectbox("Global Parish Filter", ["All Louisiana"] + all_parishes)

    filtered_df = master_df.copy()
    if selected_parish != "All Louisiana":
        filtered_df = master_df[master_df['Parish'] == selected_parish]

    # --- SECTION 5: ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    c5a, c5b = st.columns([0.6, 0.4], gap="large")
    with c5a:
        f5 = render_map(filtered_df)
        s5 = st.plotly_chart(f5, use_container_width=True, on_select="rerun", key="map5")
        if s5 and "selection" in s5 and s5["selection"]["points"]:
            new_id = str(s5["selection"]["points"][0]["location"])
            if st.session_state["active_tract"] != new_id:
                st.session_state["active_tract"] = new_id
                st.rerun()
    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        list_html = ""
        if curr in tract_centers:
            lon, lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(12).iterrows():
                list_html += f"""
                <div style='background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px;'>
                    <div style='color:#4ade80; font-size:0.65rem; font-weight:900;'>{str(a.get('Type','')).upper()}</div>
                    <div style='color:#ffffff; font-weight:700; font-size:1rem; margin: 4px 0;'>{a['Name']}</div>
                    <div style='color:#94a3b8; font-size:0.75rem;'>📍 {a['dist']:.1f} miles</div>
                </div>"""
        components.html(f"<div style='height: 530px; overflow-y: auto; font-family: sans-serif;'>{list_html}</div>", height=550)

    # --- SECTION 6: PERFECT NINE GRID ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.45, 0.55])
    with c6a:
        f6 = render_map(filtered_df, height=750)
        s6 = st.plotly_chart(f6, use_container_width=True, on_select="rerun", key="map6")
        if s6 and "selection" in s6 and s6["selection"]["points"]:
            new_id = str(s6["selection"]["points"][0]["location"])
            if st.session_state["active_tract"] != new_id:
                st.session_state["active_tract"] = new_id
                st.rerun()

    with c6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<div class='tract-header-container'><div style='font-size:2rem; font-weight:900; color:#4ade80;'>{str(d.get('Parish','')).upper()}</div><div style='color:#94a3b8;'>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
            
            m_cols = [st.columns(3) for _ in range(3)]
            metrics = [
                (d.get('Metro Status (Metropolitan/Rural)', 'N/A'), "Tract Status"),
                (d.get('NMTC_Eligible', 'No'), "NMTC Eligible"),
                (d.get('Deeply_Distressed', 'No'), "Deeply Distressed"),
                (f"{d.get('_pov_num', 0):.1f}%", "Poverty Rate"),
                (f"{d.get('_unemp_num', 0):.1f}%", "Unemployment"),
                (f"${d.get('_mfi_num', 0):,.0f}", "Median Income"),
                (d.get('Median Home Value', 'N/A'), "Home Value"),
                (d.get('Population 65 years and over', '0'), "Pop 65+"),
                (f"{d.get('Broadband Internet (%)','0')}", "Broadband")
            ]
            for i, (val, lbl) in enumerate(metrics):
                m_cols[i//3][i%3].markdown(f"<div class='metric-card'><div class='metric-value'>{val}</div><div class='metric-label'>{lbl}</div></div>", unsafe_allow_html=True)

            st.write("---")
            cat = st.selectbox("Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification")
            
            if st.button("Add to My Recommendations", type="primary", use_container_width=True):
                st.session_state["session_recs"].append({
                    "Date": datetime.now().strftime("%I:%M %p"),
                    "Tract ID": str(st.session_state["active_tract"]),
                    "Parish": str(d.get('Parish', 'N/A')),
                    "Category": cat,
                    "Justification": just
                })
                st.success(f"Tract {st.session_state['active_tract']} added to your list.")
                st.rerun()

    # --- SECTION 7: USER SESSION SPREADSHEET ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 7</div><div class='section-title'>My Recommended Tracts</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>Review the tracts you have selected during this session. This list is temporary and will be cleared when you close the browser or log out.</div>", unsafe_allow_html=True)
    
    if st.session_state["session_recs"]:
        local_df = pd.DataFrame(st.session_state["session_recs"])
        
        st.dataframe(
            local_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Justification": st.column_config.TextColumn("Rationale", width="large"),
                "Tract ID": st.column_config.TextColumn("GEOID")
            }
        )
        
        c7_left, c7_right = st.columns([0.2, 0.8])
        with c7_left:
            if st.button("Clear My List", use_container_width=True):
                st.session_state["session_recs"] = []
                st.rerun()
    else:
        st.info("Your recommendation list is currently empty. Navigate to a tract on the map and add it to see it appear here.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())