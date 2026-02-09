import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
import numpy as np
import ssl
from streamlit_gsheets import GSheetsConnection

# 0. INITIAL CONFIG
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

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
            u, p = st.session_state["username"].strip(), str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align:center; color:white; margin-top:50px;'>Louisiana OZ 2.0 Login</h2>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Secure Login", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 30px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.7rem; font-weight: 900; color: #4ade80; margin-bottom: 2px; letter-spacing: 0.1em; }
        .section-title { font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 3rem; font-weight: 900; color: #f8fafc; line-height: 1.1; margin-bottom: 10px; }
        .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 0.2em; }
        .narrative-text { font-size: 1.1rem; line-height: 1.6; color: #cbd5e1; max-width: 900px; margin-bottom: 15px; }
        .benefit-card { background: #161b28; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; margin-bottom: 15px; }
        .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    @st.cache_data(ttl=3600)
    def load_assets():
        geojson = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json") as f: geojson = json.load(f)
        else:
            geo_url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
            try:
                r = requests.get(geo_url, timeout=10, verify=False)
                if r.status_code == 200: geojson = r.json()
            except: pass

        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        # Load your files
        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        
        # Format FIPS to 11-digit strings
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
        # Tracks highlighted green are only those eligible for Opportunity Zone 2.0
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['Eligibility_Status'] = master[elig_col].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        return geojson, master, anchors

    gj, master_df, anchors_df = load_assets()

    # --- SECTION 1: HERO ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div class='hero-subtitle'>Opportunity Zones 2.0</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div>
            <div class='narrative-text'>
                Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, housing, and innovation in the communities that need it most.
            </div>
        </div>
        """, unsafe_allow_html=True)

    # --- SECTION 2: BENEFITS ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes on original capital gains for 5 years.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Qualified taxpayer receives 10% basis step-up (30% if rural).</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Zero federal capital gains tax on appreciation after 10 years.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 3: ADVOCACY ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Census Tract Advocacy</div><div class='narrative-text'>Regional driven advocacy to amplify local stakeholder needs.</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Geographically Disbursed</h3><p>Zones will be distributed throughout the state focusing on rural and investment ready tracts.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Distressed Communities</h3><p>Eligibility is dependent on the federal definition of a low-income community.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Project Ready</h3><p>Aligning regional recommendations with tracts likely to receive private investment.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 4: BEST PRACTICES ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><div class='narrative-text'>Leverage OZ 2.0 capital to catalyze community and economic development.</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Economic Innovation Group</h3><p>Proximity to ports and manufacturing hubs ensures long-term tenant demand.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Frost Brown Todd</h3><p>Utilizing local educational anchors to provide a skilled labor force.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>American Policy Institute</h3><p>Stack incentives to de-risk innovative projects. Historic Tax Credits and LIHTC are available.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 5: STATIC ASSET MAP ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Industrial & Institutional Asset Map</div>", unsafe_allow_html=True)
    if gj is not None:
        fig_5 = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", 
            color_discrete_map={"Eligible": "rgba(74, 222, 128, 0.3)", "Ineligible": "rgba(30,41,59,0.1)"},
            mapbox_style="white-bg", zoom=6, center={"lat": 31.0, "lon": -92.0}, opacity=0.5
        )
        fig_5.update_layout(
            mapbox_layers=[{
                "below": 'traces', "sourcetype": "raster",
                "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]
            }],
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=650, showlegend=False
        )
        fig_5.add_trace(go.Scattermapbox(
            lat=anchors_df['Lat'], lon=anchors_df['Lon'], mode='markers',
            marker=go.scattermapbox.Marker(size=8, color='#4ade80'),
            text=anchors_df['Name'], hoverinfo='text'
        ))
        st.plotly_chart(fig_5, use_container_width=True, key="static_map")

    # --- SECTION 6: INTERACTIVE TOOL ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 6</div><div class='section-title'>Interactive Recommendation Tool</div></div>", unsafe_allow_html=True)
    
    if "recommendation_log" not in st.session_state:
        st.session_state["recommendation_log"] = []

    if gj is not None:
        m_col, p_col = st.columns([7, 3])
        with m_col:
            fig_6 = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                color="Eligibility_Status", 
                color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.2)"},
                mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
            )
            fig_6.update_layout(
                mapbox_layers=[{
                    "below": 'traces', "sourcetype": "raster",
                    "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]
                }],
                coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, 
                paper_bgcolor='rgba(0,0,0,0)', height=600
            )
            selection = st.plotly_chart(fig_6, use_container_width=True, on_select="rerun", key="interactive_map")

        with p_col:
            active_id = None
            if selection and "selection" in selection and selection["selection"]["points"]:
                active_id = selection["selection"]["points"][0].get("location")

            if active_id:
                row = master_df[master_df["geoid_str"] == str(active_id)]
                if not row.empty:
                    d = row.iloc[0]
                    st.markdown(f"### Tract: {active_id}")
                    st.markdown(f"<h4 style='color:#4ade80;'>{str(d.get('Parish', 'LOUISIANA')).upper()}</h4>", unsafe_allow_html=True)
                    justification = st.text_area("Narrative Input", placeholder="Why this tract?", height=150)
                    if st.button("Log Recommendation", use_container_width=True, type="primary"):
                        st.session_state["recommendation_log"].append({
                            "Tract": active_id, "Parish": d.get('Parish'), "Narrative": justification
                        })
                        st.rerun()
            else:
                st.info("Select a tract on the map to begin.")

    if st.session_state["recommendation_log"]:
        st.write("---")
        st.markdown("### 📋 Final Recommendations")
        st.dataframe(pd.DataFrame(st.session_state["recommendation_log"]), use_container_width=True, hide_index=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())