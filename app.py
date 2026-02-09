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

# --- 1. AUTHENTICATION (CONDENSED MODERN / BLACK INPUT TEXT) ---
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
            
            .login-title { 
                font-family: 'Inter', sans-serif; 
                font-size: 1.5rem; 
                font-weight: 900; 
                color: #ffffff; 
                margin-bottom: 4px;
                letter-spacing: -0.03em;
            }
            
            .login-tag {
                font-family: 'Inter', sans-serif;
                font-size: 0.7rem;
                color: #4ade80;
                text-transform: uppercase;
                letter-spacing: 0.15em;
                margin-bottom: 25px;
            }
            
            /* Labels are white */
            label, p, .stText {
                color: #ffffff !important;
                font-weight: 600 !important;
                font-size: 0.85rem !important;
            }

            /* Input box container remains light for contrast */
            div[data-baseweb="input"] {
                background-color: #f8fafc !important; /* Off-white/Light Gray background */
                border: 1px solid #374151 !important;
                border-radius: 6px !important;
            }
            
            /* The ACTUAL text entered by the user is black */
            input {
                color: #000000 !important;
                -webkit-text-fill-color: #000000 !important;
                font-family: 'Inter', sans-serif !important;
                font-weight: 500 !important;
            }
            </style>
            
            <div class="login-card">
                <div class="login-title">OZ 2.0 Portal</div>
                <div class="login-tag">Secure Stakeholder Access</div>
            </div>
        """, unsafe_allow_html=True)
        
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.write("") 
            st.button("Sign In", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)

    # --- 2. GLOBAL STYLING (POST-LOGIN) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        
        html, body, [class*="stApp"], [data-testid="stVerticalBlock"] { 
            font-family: 'Inter', sans-serif !important; 
            background-color: #0b0f19 !important; 
            color: #ffffff; 
        }
        
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; line-height: 1.1; }
        .hero-subtitle { color: #4ade80; font-size: 1.1rem; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 5px;}
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; }

        .benefit-card { 
            background-color: #111827 !important; 
            padding: 25px; 
            border: 1px solid #2d3748; 
            border-radius: 8px; 
            min-height: 220px;
            box-shadow: none !important;
            transition: all 0.3s ease-in-out;
        }
        .benefit-card:hover {
            border-color: #4ade80 !important;
            transform: translateY(-5px);
            background-color: #161b28 !important;
        }
        .benefit-card h3 { color: #f8fafc; font-size: 1.2rem; font-weight: 700; margin-bottom: 10px; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }

        .metric-card { 
            background-color: #111827 !important; 
            padding: 8px; 
            border: 1px solid #1e293b; 
            border-radius: 8px; 
            text-align: center; 
            height: 85px; 
            display: flex; 
            flex-direction: column; 
            justify-content: center; 
            margin-bottom: 8px;
            box-shadow: none !important;
        }
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 3px; }
        
        .tract-header-container { 
            background-color: #111827 !important; 
            padding: 20px 25px; 
            border-radius: 10px; 
            border-top: 4px solid #4ade80; 
            margin-bottom: 15px;
            border-left: 1px solid #1e293b;
            border-right: 1px solid #1e293b;
            border-bottom: 1px solid #1e293b;
        }
        .header-parish { font-size: 2.2rem; font-weight: 900; color: #4ade80; text-transform: uppercase; margin-bottom: 5px; }
        .header-sub-row { display: flex; justify-content: space-between; border-top: 1px solid #1e293b; padding-top: 10px; }
        .header-label { color: #94a3b8; font-size: 0.7rem; font-weight: 700; text-transform: uppercase; }
        .header-value { font-weight: 700; color: #ffffff; }

        .stTextArea textarea { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
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
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        anchors = read_csv_safe("la_anchors.csv")
        centers = {}
        if geojson:
            for feature in geojson['features']:
                props = feature['properties']
                geoid = props.get('GEOID') or props.get('GEOID20')
                try:
                    if feature['geometry']['type'] == 'Polygon':
                        coords = np.array(feature['geometry']['coordinates'][0])
                    else:
                        coords = np.array(feature['geometry']['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map(df, height=600):
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#cbd5e1"},
                                     mapbox_style="carto-positron", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.5)
        fig.update_traces(below='traces')
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

    # --- SECTIONS 2, 3, 4: FRAMEWORK ---
    sections_data = [
        ("SECTION 2", "The OZ 2.0 Benefit Framework", [
            ("Capital Gain Deferral", "Defer taxes on original capital gains for 5 years."),
            ("Basis Step-Up", "Qualified taxpayer receives 10% basis step-up (30% if rural)."),
            ("Permanent Exclusion", "Zero federal capital gains tax on appreciation after 10 years.")
        ]),
        ("SECTION 3", "Census Tract Advocacy", [
            ("Geographically Disbursed", "Zones will be distributed throughout the state focusing on rural and investment ready tracts."),
            ("Distressed Communities", "Eligibility is dependent on the federal definition of a low-income community."),
            ("Project Ready", "Aligning regional recommendations with tracts likely to receive private investment.")
        ]),
        ("SECTION 4", "Best Practices", [
            ("Economic Innovation Group", "Proximity to ports and manufacturing hubs ensures long-term tenant demand."),
            ("Frost Brown Todd", "Utilizing local educational anchors to provide a skilled labor force."),
            ("American Policy Institute", "Stack incentives to de-risk projects for long-term growth.")
        ])
    ]
    for num, title, cards in sections_data:
        st.markdown(f"<div class='content-section'><div class='section-num'>{num}</div><div class='section-title'>{title}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, (ct, ctx) in enumerate(cards):
            cols[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    c5a, c5b = st.columns([0.6, 0.4], gap="large")
    with c5a:
        f5 = render_map(master_df)
        s5 = st.plotly_chart(f5, use_container_width=True, on_select="rerun", key="map5")
        if s5 and s5.get("selection", {}).get("points"): st.session_state["active_tract"] = str(s5["selection"]["points"][0]["location"])
    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800; margin-bottom:10px;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        anchor_style = "<style>.anchor-item { background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px; transition: all 0.2s ease; cursor: default; } .anchor-item:hover { border-color: #4ade80; background: #161b28; }</style>"
        list_html = anchor_style
        if curr in tract_centers:
            lon, lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(12).iterrows():
                list_html += f"<div class='anchor-item'><div style='color:#4ade80; font-size:0.65rem; font-weight:900;'>{str(a.get('Type','')).upper()}</div><div style='font-weight:700; color:#f8fafc; font-size:0.9rem;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.75rem;'>📍 {a['dist']:.1f} miles</div></div>"
        components.html(f"<div style='height: 530px; overflow-y: auto; padding-right:5px;'>{list_html}</div>", height=550)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.5, 0.5])
    with c6a:
        f6 = render_map(master_df, height=750)
        s6 = st.plotly_chart(f6, use_container_width=True, on_select="rerun", key="map6")
        if s6 and s6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(s6["selection"]["points"][0]["location"])
    with c6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"""
                <div class='tract-header-container'>
                    <div class='header-parish'>{str(d.get('Parish','')).upper()}</div>
                    <div class='header-sub-row'>
                        <div><div class='header-label'>TRACT ID</div><div class='header-value'>{st.session_state['active_tract']}</div></div>
                        <div style='text-align:right;'><div class='header-label'>REGION</div><div class='header-value'>{str(d.get('Region','')).upper()}</div></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            r1 = st.columns(3)
            r1[0].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            r1[1].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            r1[2].markdown(f"<div class='metric-card'><div class='metric-value'>${float(str(d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')).replace(',','').replace('$','')):,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
            
            r2 = st.columns(3)
            r2[0].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Median Home Value', 'N/A')}</div><div class='metric-label'>Home Value</div></div>", unsafe_allow_html=True)
            r2[1].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Population 65 years and over', '0')}</div><div class='metric-label'>Pop (65+)</div></div>", unsafe_allow_html=True)
            r2[2].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Broadband Internet (%)','0')}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)

            st.write("---")
            cat = st.selectbox("Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification")
            if st.button("Submit Official Recommendation", type="primary", use_container_width=True):
                new_rec = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": str(st.session_state["active_tract"]), "Category": cat, "Justification": just, "User": st.session_state["current_user"]}])
                conn.create(worksheet="Sheet1", data=new_rec)
                st.success("Recommendation logged.")
                st.rerun()

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear()) 