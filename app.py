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
            .login-title { font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 900; color: #ffffff; margin-bottom: 4px; letter-spacing: -0.03em; }
            .login-tag { font-family: 'Inter', sans-serif; font-size: 0.7rem; color: #4ade80; text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 25px; }
            label, p, .stText { color: #ffffff !important; font-weight: 600 !important; font-size: 0.85rem !important; }
            div[data-baseweb="input"] { background-color: #f8fafc !important; border: 1px solid #374151 !important; border-radius: 6px !important; }
            input { color: #000000 !important; -webkit-text-fill-color: #000000 !important; font-family: 'Inter', sans-serif !important; font-weight: 500 !important; }
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

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"], [data-testid="stVerticalBlock"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 220px; transition: all 0.3s ease-in-out; }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); background-color: #161b28 !important; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 12px; }
        .metric-value { font-size: 1.0rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 4px; line-height: 1.2; }
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; margin-bottom: 15px; border: 1px solid #1e293b; }
        .header-parish { font-size: 2.2rem; font-weight: 900; color: #4ade80; text-transform: uppercase; margin-bottom: 5px; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    @st.cache_data(ttl=3600)
    def load_assets():
        geojson = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: geojson = json.load(f)
        master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible')
        anchors = pd.read_csv("la_anchors.csv")
        return geojson, master, anchors

    gj, master_df, anchors_df = load_assets()

    def render_map(df, height=600):
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#cbd5e1"},
                                     mapbox_style="carto-positron", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.5)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height)
        return fig

    # --- SECTION 6: TRACT PROFILING (NINE METRIC CARDS) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.45, 0.55])
    
    with c6a:
        f6 = render_map(master_df, height=800)
        s6 = st.plotly_chart(f6, use_container_width=True, on_select="rerun", key="map6")
        if s6 and s6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(s6["selection"]["points"][0]["location"])
    
    with c6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<div class='tract-header-container'><div class='header-parish'>{str(d.get('Parish','')).upper()}</div><div style='color:#94a3b8; font-size:0.8rem; font-weight:700;'>TRACT: {st.session_state['active_tract']} | {str(d.get('Region','')).upper()}</div></div>", unsafe_allow_html=True)
            
            # --- THE NINE CARDS GRID ---
            # Row 1: Eligibility & Status
            r1c1, r1c2, r1c3 = st.columns(3)
            r1c1.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Urban/Rural status', 'N/A')}</div><div class='metric-label'>Tract Status</div></div>", unsafe_allow_html=True)
            r1c2.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('NMTC Eligibility', 'No')}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            r1c3.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Deeply Distressed status', 'No')}</div><div class='metric-label'>Deeply Distressed</div></div>", unsafe_allow_html=True)

            # Row 2: Economic Metrics
            r2c1, r2c2, r2c3 = st.columns(3)
            r2c1.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            r2c2.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            r2c3.markdown(f"<div class='metric-card'><div class='metric-value'>${float(str(d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')).replace(',','').replace('$','')):,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)

            # Row 3: Community Metrics
            r3c1, r3c2, r3c3 = st.columns(3)
            r3c1.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Median Home Value', 'N/A')}</div><div class='metric-label'>Median Home Value</div></div>", unsafe_allow_html=True)
            r3c2.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Population 65 years and over', '0')}</div><div class='metric-label'>Population (65+)</div></div>", unsafe_allow_html=True)
            r3c3.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Broadband Internet (%)','0')}%</div><div class='metric-label'>Broadband Access</div></div>", unsafe_allow_html=True)

            st.write("---")
            cat = st.selectbox("Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification")
            if st.button("Submit Official Recommendation", type="primary", use_container_width=True):
                new_rec = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": str(st.session_state["active_tract"]), "Category": cat, "Justification": just, "User": st.session_state["current_user"]}])
                conn.create(worksheet="Sheet1", data=new_rec)
                st.success("Recommendation logged.")
                st.rerun()

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())