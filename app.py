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

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

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
            .login-card { max-width: 360px; margin: 140px auto 20px auto; padding: 30px; background: #111827; border: 1px solid #1e293b; border-top: 4px solid #4ade80; border-radius: 12px; text-align: center; }
            label, p, .stText { color: #ffffff !important; font-weight: 600 !important; }
            div[data-baseweb="input"] { background-color: #f8fafc !important; border-radius: 6px !important; }
            input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; }
            </style>
            <div class="login-card"><div style="font-family:'Inter'; font-size:1.5rem; font-weight:900; color:white;">OZ 2.0 Portal</div></div>
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
        
        /* SECTIONS 2-4 GREEN HOVER CARDS */
        .benefit-card { 
            background-color: #111827 !important; 
            padding: 25px; 
            border: 1px solid #2d3748; 
            border-radius: 8px; 
            min-height: 220px; 
            transition: all 0.3s ease-in-out; 
        }
        .benefit-card:hover { 
            border-color: #4ade80 !important; 
            transform: translateY(-5px); 
            background-color: #161b28 !important; 
            box-shadow: 0 10px 30px -10px rgba(74, 222, 128, 0.2);
        }
        .benefit-card h3 { color: #f8fafc; font-size: 1.2rem; font-weight: 700; margin-bottom: 10px; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }

        /* SECTION 6 METRIC CARDS */
        .metric-card { 
            background-color: #111827 !important; padding: 15px; border: 1px solid #1e293b; border-radius: 12px; 
            text-align: center; height: 115px; display: flex; flex-direction: column; justify-content: center; 
            margin-bottom: 15px; transition: all 0.2s ease;
        }
        .metric-card:hover { border-color: #4ade80; background-color: #161b28 !important; }
        .metric-value { font-size: 1.3rem; font-weight: 900; color: #4ade80; line-height: 1; }
        .metric-label { font-size: 0.65rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.08em; margin-top: 8px; font-weight: 700; }
        
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; border: 1px solid #1e293b; margin-bottom: 15px;}
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
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible')
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
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#cbd5e1"},
                                     mapbox_style="carto-positron", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.5)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height)
        return fig

    # --- SECTION 1: HERO ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div style="color: #4ade80; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase;">Opportunity Zones 2.0</div>
            <div style="font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px;">Louisiana Opportunity Zone 2.0 Recommendation Portal</div>
            <div style="font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px;">Louisiana’s pathway to long-term private capital, fueling jobs and innovation in the communities that need it most.</div>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTIONS 2-4 ---
    for num, title, cards in [
        ("SECTION 2", "The OZ 2.0 Benefit Framework", [
            ("Capital Gain Deferral", "Defer taxes on original capital gains for 5 years."),
            ("Basis Step-Up", "Qualified taxpayer receives 10% basis step-up (30% if rural)."),
            ("Permanent Exclusion", "Zero federal capital gains tax on appreciation after 10 years.")
        ]),
        ("SECTION 3", "Census Tract Advocacy", [
            ("Geographically Disbursed", "Zones focused on rural and investment-ready tracts."),
            ("Distressed Communities", "Eligibility follows federal low-income definitions."),
            ("Project Ready", "Aligning recommendations with private investment targets.")
        ]),
        ("SECTION 4", "Best Practices", [
            ("Economic Innovation Group", "Proximity to ports ensures long-term tenant demand."),
            ("Frost Brown Todd", "Utilizing educational anchors for a skilled labor force."),
            ("American Policy Institute", "Stack incentives to de-risk projects for growth.")
        ])
    ]:
        st.markdown(f"<div class='content-section'><div class='section-num'>{num}</div><div class='section-title'>{title}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, (ct, ctx) in enumerate(cards):
            cols[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: HIGH-END ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    c5a, c5b = st.columns([0.6, 0.4], gap="large")
    with c5a:
        f5 = render_map(master_df)
        s5 = st.plotly_chart(f5, use_container_width=True, on_select="rerun", key="map5")
        if s5 and s5.get("selection", {}).get("points"): st.session_state["active_tract"] = str(s5["selection"]["points"][0]["location"])
    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800; margin-bottom:15px;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        
        anchor_html = """
        <style>
            .anchor-card {
                background: #111827;
                border: 1px solid #1e293b;
                padding: 16px;
                border-radius: 12px;
                margin-bottom: 12px;
                transition: all 0.2s ease;
            }
            .anchor-card:hover { border-color: #4ade80; background: #161b28; }
            .anchor-name { font-weight: 800; color: #f8fafc; font-size: 1.05rem; margin-bottom: 6px; }
            .anchor-type-tag {
                display: inline-block;
                background: rgba(74, 222, 128, 0.1);
                color: #4ade80;
                font-size: 0.6rem;
                font-weight: 900;
                padding: 2px 8px;
                border-radius: 4px;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 8px;
            }
            .anchor-dist { color: #64748b; font-size: 0.75rem; font-weight: 600; }
        </style>
        """
        if curr in tract_centers:
            lon, lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(15).iterrows():
                anchor_html += f"""
                <div class='anchor-card'>
                    <div class='anchor-type-tag'>{str(a.get('Type','')).upper()}</div>
                    <div class='anchor-name'>{a['Name']}</div>
                    <div class='anchor-dist'>📍 {a['dist']:.1f} miles away</div>
                </div>
                """
        components.html(f"<div style='height: 540px; overflow-y: auto; padding-right:10px;'>{anchor_html}</div>", height=550)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.45, 0.55])
    with c6a:
        f6 = render_map(master_df, height=750)
        s6 = st.plotly_chart(f6, use_container_width=True, on_select="rerun", key="map6")
        if s6 and s6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(s6["selection"]["points"][0]["location"])
    with c6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<div class='tract-header-container'><div style='font-size:2rem; font-weight:900; color:#4ade80;'>{str(d.get('Parish','')).upper()}</div><div style='color:#94a3b8;'>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
            
            m_cols = [st.columns(3) for _ in range(3)]
            metrics = [
                (d.get('Urban/Rural status', 'N/A'), "Tract Status"),
                (d.get('NMTC Eligibility', 'No'), "NMTC Eligible"),
                (d.get('Deeply Distressed status', 'No'), "Deeply Distressed"),
                (f"{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)}%", "Poverty Rate"),
                (f"{d.get('Unemployment Rate (%)','0')}%", "Unemployment"),
                (f"${float(str(d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')).replace(',','').replace('$','')):,.0f}", "Median Income"),
                (d.get('Median Home Value', 'N/A'), "Home Value"),
                (d.get('Population 65 years and over', '0'), "Pop 65+"),
                (f"{d.get('Broadband Internet (%)','0')}%", "Broadband")
            ]
            for i, (val, lbl) in enumerate(metrics):
                m_cols[i//3][i%3].markdown(f"<div class='metric-card'><div class='metric-value'>{val}</div><div class='metric-label'>{lbl}</div></div>", unsafe_allow_html=True)

            st.write("---")
            cat = st.selectbox("Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification")
            if st.button("Submit Recommendation", type="primary", use_container_width=True):
                new_rec = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": str(st.session_state["active_tract"]), "Category": cat, "Justification": just, "User": st.session_state["current_user"]}])
                conn.create(worksheet="Sheet1", data=new_rec)
                st.success("Recommendation logged.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())