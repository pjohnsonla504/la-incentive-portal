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
        st.markdown("<div style='text-align:center; padding:50px;'><h1 style='color:white;'>Louisiana OZ 2.0 Login</h1></div>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Secure Login", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        
        /* Section Styling */
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        
        /* FIXED SIZE BENEFIT CARDS (Sections 2, 3, 4) */
        .benefit-card { 
            background: #161b28; 
            padding: 25px; 
            border: 1px solid #2d3748; 
            border-radius: 8px; 
            min-height: 220px; 
            display: flex; 
            flex-direction: column; 
            justify-content: flex-start;
            transition: 0.3s;
        }
        .benefit-card:hover { border-color: #4ade80; }
        .benefit-card h3 { margin-top: 0; color: #f8fafc; font-size: 1.2rem; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }

        /* Metric Cards */
        .metric-card { background: #111827; padding: 8px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 8px;}
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 3px; }
        
        /* Justification Text White Override */
        .stTextArea textarea { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
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
        return geojson, master

    gj, master_df = load_assets()

    # --- SECTIONS 2, 3, 4 (Standardized Cards) ---
    sections = [
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

    for num, title, cards in sections:
        st.markdown(f"<div class='content-section'><div class='section-num'>{num}</div><div class='section-title'>{title}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, (card_title, card_text) in enumerate(cards):
            cols[i].markdown(f"<div class='benefit-card'><h3>{card_title}</h3><p>{card_text}</p></div>", unsafe_allow_html=True)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    col6_map, col6_data = st.columns([0.5, 0.5])
    
    with col6_map:
        fig6 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="carto-darkmatter", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        fig6.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=750, clickmode='event+select')
        sel6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="map_s6_final")
        if sel6 and sel6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel6["selection"]["points"][0]["location"])

    with col6_data:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            poverty_rate = float(d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0))
            med_income = float(str(d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')).replace(',','').replace('$',''))
            home_val_raw = str(d.get('Estimate!!Median value (dollars)', '0')).replace(',','').replace('$','')
            home_val = f"${float(home_val_raw):,.0f}" if home_val_raw.isdigit() else "N/A"

            st.markdown(f"<div style='background:#111827; padding:20px; border-radius:10px; border-left: 5px solid #4ade80; margin-bottom:15px;'><h2 style='margin:0;'>{st.session_state['active_tract']}</h2><p style='color:#4ade80; font-weight:700;'>{str(d.get('Parish','')).upper()}</p></div>", unsafe_allow_html=True)
            
            # Metric Rows
            for cols in [st.columns(3), st.columns(3), st.columns(3)]:
                pass # Structure only
            
            # Row 1: Status
            r1 = st.columns(3)
            r1[0].markdown(f"<div class='metric-card'><div class='metric-value'>{'URBAN' if 'metropolitan' in str(d.get('Metro Status','')).lower() else 'RURAL'}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            r1[1].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if poverty_rate > 20 else 'NO'}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            r1[2].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if poverty_rate > 40 else 'NO'}</div><div class='metric-label'>Deeply Distressed</div></div>", unsafe_allow_html=True)

            # Row 2: Economics
            r2 = st.columns(3)
            r2[0].markdown(f"<div class='metric-card'><div class='metric-value'>{poverty_rate}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            r2[1].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            r2[2].markdown(f"<div class='metric-card'><div class='metric-value'>${med_income:,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)

            # Row 3: Housing/Demographics
            r3 = st.columns(3)
            r3[0].markdown(f"<div class='metric-card'><div class='metric-value'>{home_val}</div><div class='metric-label'>Median Home Value</div></div>", unsafe_allow_html=True)
            r3[1].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Total!!Total population!!65 years and over','0')}</div><div class='metric-label'>Pop (65+)</div></div>", unsafe_allow_html=True)
            r3[2].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Broadband Internet (%)','0')}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            cat = st.selectbox("Justification Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification", height=120)
            
            if st.button("Submit Official Recommendation", type="primary", use_container_width=True):
                try:
                    new_rec = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": str(st.session_state["active_tract"]), "Category": cat, "Justification": just, "User": st.session_state["current_user"]}])
                    conn.create(worksheet="Sheet1", data=new_rec)
                    st.success("Recommendation logged to Sheet1")
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

    # History Table
    st.markdown("### My Recommendations (Sheet1)")
    try:
        all_recs = conn.read(worksheet="Sheet1", ttl="5s")
        st.dataframe(all_recs[all_recs['User'].astype(str) == st.session_state["current_user"]], use_container_width=True, hide_index=True)
    except: st.info("No recommendations found.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())