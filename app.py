import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

# 0. INITIAL CONFIG
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Force SSL Bypass for Cloud Environments
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            entered_user = st.session_state["username"].strip()
            entered_pass = str(st.session_state["password"]).strip()
            if entered_user in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == entered_user]
                if str(user_row['password'].values[0]).strip() == entered_pass:
                    st.session_state["password_correct"] = True
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if "password_correct" not in st.session_state:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
            .stApp { background-color: #0b0f19; }
            .login-box {
                max-width: 450px;
                margin: 40px auto 10px auto;
                padding: 30px;
                background: #111827;
                border: 1px solid #1e293b;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }
            .login-title { font-family: 'Playfair Display', serif; font-size: 2rem; font-weight: 900; color: #f8fafc; margin-bottom: 8px; }
            .login-subtitle { font-size: 0.7rem; color: #4ade80; font-weight: 800; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 20px; }
            </style>
            <div class="login-box">
                <div class="login-subtitle">Louisiana Opportunity Zones 2.0</div>
                <div class="login-title">Recommendation Portal</div>
            </div>
        """, unsafe_allow_html=True)
        
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Secure Login", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():

    # --- 2. GLOBAL STYLING (Compact Padding) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 30px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.7rem; font-weight: 900; color: #4ade80; margin-bottom: 2px; letter-spacing: 0.1em; }
        .section-title { font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 3rem; font-weight: 900; line-height: 1.1; color: #f8fafc; margin-bottom: 10px; }
        .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 0.2em; }
        .narrative-text { font-size: 1.1rem; line-height: 1.6; color: #cbd5e1; max-width: 900px; }
        .benefit-card { background: #161b28; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    @st.cache_data(ttl=3600)
    def load_assets():
        geojson = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json") as f:
                geojson = json.load(f)
        if not geojson:
            geo_url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
            try:
                r = requests.get(geo_url, timeout=10, verify=False)
                if r.status_code == 200: geojson = r.json()
            except: pass

        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['Eligibility_Status'] = master[elig_col].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible')
        return geojson, master, anchors

    gj, master_df, anchors_df = load_assets()

    # --- SECTIONS 1-4 (Consistent Height) ---
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana OZ 2.0 Recommendation Portal</div><div class='narrative-text'>Unlocking long-term private capital to fuel jobs, housing, and innovation.</div></div>""", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Deferral</h3><p>Defer taxes on original capital gains for 5 years.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Step-Up</h3><p>10% basis step-up (30% if rural).</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Exclusion</h3><p>Zero federal capital gains tax after 10 years.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Census Tract Advocacy</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Disbursed</h3><p>Zones distributed throughout rural and urban tracts.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Distressed</h3><p>Focus on low-income community definitions.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Project Ready</h3><p>Aligning recommendations with private investment.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>EIG</h3><p>Proximity to ports ensures tenant demand.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>FBT</h3><p>Utilizing educational anchors for labor.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>API</h3><p>Stack incentives to de-risk projects.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAP (SHRUNK TO 500PX) ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 5</div>
            <div class='section-title'>Industrial & Community Assets</div>
        </div>
    """, unsafe_allow_html=True)
    
    if not anchors_df.empty:
        selected_types = st.multiselect("Filter Asset Type:", options=sorted(anchors_df['Type'].unique().tolist()), default=sorted(anchors_df['Type'].unique().tolist()))
        filtered_anchors = anchors_df[anchors_df['Type'].isin(selected_types)]

        fig_assets = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", 
            color_discrete_map={"Eligible": "rgba(74, 222, 128, 0.15)", "Ineligible": "rgba(30,41,59,0.05)"},
            mapbox_style="carto