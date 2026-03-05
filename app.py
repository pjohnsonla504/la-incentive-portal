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

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

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

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["user_login_input"].strip()
            p = str(st.session_state["pass_login_input"]).strip()
            
            # Case-insensitive check
            user_match = users_df[users_df['username'].astype(str).str.lower() == u.lower()]
            
            if not user_match.empty:
                if str(user_match['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = u
                    return
            st.session_state["password_correct"] = False
            st.error("Invalid username or password")
        except Exception as e:
            st.error(f"Error connecting to database: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
            .stApp { background-color: #0b0f19 !important; font-family: 'Inter', sans-serif; }
            div[data-testid="stVerticalBlock"] > div:has(input) {
                background-color: #111827; padding: 40px; border-radius: 15px;
                border: 1px solid #1e293b; box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }
            label { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; }
            input { background-color: #0b0f19 !important; color: white !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; }
            button[kind="primary"], .stButton > button { background-color: #4ade80 !important; color: #0b0f19 !important; font-weight: 900 !important; border: none !important; height: 3em !important; margin-top: 10px; }
            .login-header { text-align: center; margin-bottom: 2rem; }
            </style>
        """, unsafe_allow_html=True)

        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<div class='login-header'><h1 style='color: white; font-weight: 900;'>OZ 2.0 Portal</h1></div>", unsafe_allow_html=True)
            with st.container():
                st.text_input("Username", key="user_login_input", placeholder="Enter your username")
                st.text_input("Password", type="password", key="pass_login_input", placeholder="••••••••")
                st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING & NAVIGATION ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 9999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .nav-link:hover { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; margin-bottom: 20px; line-height: 1.1; }
        .narrative-text { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; min-height: 250px; }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 15px; font-weight: 800; }
        .metric-card { background-color: #111827; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; }
        </style>
        <div class="nav-container">
            <a class="nav-link" href="#section-1">Overview</a>
            <a class="nav-link" href="#section-2">Benefits</a>
            <a class="nav-link" href="#section-3">Strategy</a>
            <a class="nav-link" href="#section-4">Best Practices</a>
            <a class="nav-link" href="#section-5">Mapping</a>
            <a class="nav-link" href="#section-6">Report</a>
        </div>
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
        
        master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1', 'true'] else 'Ineligible'
        )
        
        anchors = pd.read_csv("la_anchors.csv")
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    if geom['type'] == 'Polygon': pts = np.array(geom['coordinates'][0])
                    elif geom['type'] == 'MultiPolygon': pts = np.array(geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- 4. NARRATIVE SECTIONS 1-4 ---
    st.markdown("<div id='section-1'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div><div class='narrative-text'>The Opportunity Zones Program is a federal capital gains tax incentive program designed to drive long-term investments to low-income communities. Federal bill H.R. 1 (OBBBA) signed into law July 2025 strengthens the program and makes the tax incentive permanent.</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div id='section-2'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Benefit Framework</div><div class='narrative-text'>Opportunity Zones encourage investment by providing a series of capital gains tax incentives for qualifying activities in designated areas.</div></div>", unsafe_allow_html=True)
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Starting on the date of the investment, Investors may defer taxes on capital gains that are reinvested in a QOF for up to five years.</p></div>", unsafe_allow_html=True)
    with b_col2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>After 5 years, investors receive a 10% increase in basis (urban) or a 30% increase for Rural Opportunity Funds (QROF).</p></div>", unsafe_allow_html=True)
    with b_col3: st.markdown("<div class='benefit-card'><h3>10-Year Gain Exclusion</h3><p>If held for 10+ years, all new capital gains from the sale of the QOZ investment are permanently excluded from taxable income.</p></div>", unsafe_allow_html=True)

    st.markdown("<div id='section-3'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Tract Advocacy</div><div class='narrative-text'>The most effective OZ selections combine community need, investment readiness, and policy alignment. Focusing on anchor density ensures long-term economic activity and infrastructure.</div></div>", unsafe_allow_html=True)

    st.markdown("<div id='section-4'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>National Best Practices</div><div class='narrative-text'>Louisiana's framework is built upon successful models and guidance from the Economic Innovation Group (EIG) and the America First Policy Institute.</div></div>", unsafe_allow_html=True)

    # --- 5. MAPPING SECTION ---
    st.markdown("<div id='section-5'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping</div></div>", unsafe_allow_html=True)
    
    selected_parish = st.selectbox("Select Parish", ["All Louisiana"] + sorted(master_df['Parish'].unique().tolist()))
    filtered_df = master_df if selected_parish == "All Louisiana" else master_df[master_df['Parish'] == selected_parish]

    def render_map_go(df):
        map_df = df.copy()
        # 0: Ineligible, 1: Eligible, 2: Active Highlight
        map_df['Color_Val'] = map_df.apply(lambda r: 2 if r['geoid_str'] == st.session_state["active_tract"] else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Val'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#1e293b'], [0.5, '#4ade80'], [1, '#f97316']],
            showscale=False, marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        fig.update_layout(mapbox=dict(style="carto-darkmatter", zoom=6, center={"lat": 30.9, "lon": -91.8}), margin={"r":0,"t":0,"l":0,"b":0}, height=600)
        return fig

    map_event = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="main_map")
    
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state["active_tract"] = str(map_event["selection"]["points"][0]["location"])

    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr].iloc[0]
        st.subheader(f"Tract Analysis: {curr} ({row['Parish']})")
        
        m_col1, m_col2, m_col3 = st.columns(3)
        m_col1.markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Status</div></div>", unsafe_allow_html=True)
        m_col2.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
        m_col3.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['Eligibility_Status'] == 'Eligible' else 'NO'}</div><div class='metric-label'>Eligible</div></div>", unsafe_allow_html=True)

        rec_cat = st.selectbox("Strategic Category", ["Housing", "Business Development", "Infrastructure", "Technology"])
        just = st.text_area("Justification for Recommendation")
        if st.button("Add to Draft"):
            st.session_state["session_recs"].append({
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "User": st.session_state["username"],
                "Tract": curr, "Parish": row['Parish'], "Category": rec_cat, "Justification": just
            })
            st.toast("Added to report!")

    # --- 6. REPORT & MASTER SUBMISSION ---
    st.markdown("<div id='section-6'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    
    if st.session_state["session_recs"]:
        report_df = pd.DataFrame(st.session_state["session_recs"])
        st.table(report_df)
        
        if st.button("Submit Report to Master_Submissions", type="primary", use_container_width=True):
            try:
                conn = st.connection("gsheets", type=GSheetsConnection)
                
                # Appending Logic
                try:
                    existing = conn.read(worksheet="Master_Submissions")
                    final_df = pd.concat([existing, report_df], ignore_index=True)
                except:
                    final_df = report_df
                
                conn.update(worksheet="Master_Submissions", data=final_df)
                st.balloons()
                st.success(f"Report successfully uploaded by {st.session_state['username']}!")
                st.session_state["session_recs"] = []
                st.rerun()
            except Exception as e:
                st.error(f"Submission Failed: {e}")
    else:
        st.info("Select a tract on the map and add it to the draft to generate a report.")

    st.markdown("<p style='text-align:center; color:#475569; padding: 50px;'>Louisiana OZ 2.0 Admin Portal | 2026</p>", unsafe_allow_html=True)