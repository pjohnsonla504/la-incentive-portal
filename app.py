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

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 

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
            u = st.session_state["username"].strip()
            p = str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
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
            .login-box { max-width: 450px; margin: 80px auto 20px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
            .login-title { font-family: 'Playfair Display', serif; font-size: 2.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 8px; }
            .login-subtitle { font-size: 0.8rem; color: #4ade80; font-weight: 800; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 30px; }
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

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 4.2rem; font-weight: 900; line-height: 1.1; color: #f8fafc; margin-bottom: 15px; }
        .hero-subtitle { font-size: 1rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 30px; letter-spacing: 0.2em; }
        .narrative-text { font-size: 1.2rem; line-height: 1.8; color: #cbd5e1; max-width: 900px; margin-bottom: 20px; }
        
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; min-height: 280px; transition: 0.3s; }
        .benefit-card:hover { border-color: #4ade80; transform: translateY(-5px); }
        
        .side-pane-container { height: 650px; overflow-y: auto; padding-right: 15px; scrollbar-width: thin; scrollbar-color: #4ade80 #0b0f19; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.6rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.7rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }
        
        .anchor-pill { background: rgba(255, 255, 255, 0.03); border: 1px solid #1e293b; padding: 15px; border-radius: 8px; margin-bottom: 10px; }
        .anchor-pill:hover { border-color: #4ade80; background: rgba(74, 222, 128, 0.05); }
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
        # Fixing column mapping for GEOID
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        
        anchors = read_csv_safe("la_anchors.csv")
        anchors['Lat'] = pd.to_numeric(anchors['Lat'], errors='coerce')
        anchors['Lon'] = pd.to_numeric(anchors['Lon'], errors='coerce')
        anchors = anchors.dropna(subset=['Lat', 'Lon'])

        centers = {}
        if geojson:
            for feature in geojson['features']:
                props = feature['properties']
                geoid = props.get('GEOID') or props.get('GEOID20')
                try:
                    coords = np.array(feature['geometry']['coordinates'][0]) if feature['geometry']['type'] == 'Polygon' else np.array(feature['geometry']['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTIONS 1-4 (CONTENT RESTORED) ---
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div><div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, housing, and innovation in the communities that need it most.</div></div>""", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes on original capital gains for 5 years.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Qualified taxpayer receives 10% basis step-up (30% if rural).</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Zero federal capital gains tax on appreciation after 10 years.</p></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Census Tract Advocacy</div><div class='narrative-text'>Regional driven advocacy to amplify local stakeholder needs.</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Geographically Disbursed</h3><p>Zones will be distributed throughout the state focusing on rural and investment ready tracts.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Distressed Communities</h3><p>Eligibility is dependent on the federal definition of a low-income community.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Project Ready</h3><p>Aligning regional recommendations with tracts likely to receive private investment.</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><div class='narrative-text'>Leverage OZ 2.0 capital to catalyze community and economic development.</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Economic Innovation Group</h3><p>Proximity to ports and manufacturing hubs ensures long-term tenant demand.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Frost Brown Todd</h3><p>Utilizing local educational anchors to provide a skilled labor force.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>American Policy Institute</h3><p>Stack incentives to de-risk projects.</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: SIDE-BY-SIDE ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div></div>", unsafe_allow_html=True)
    col5_left, col5_right = st.columns([6, 4])
    
    with col5_left:
        fig5 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        fig5.update_layout(mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                           margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650, clickmode='event+select')
        sel5 = st.plotly_chart(fig5, use_container_width=True, on_select="rerun", key="map_v5_sync")
        if sel5 and sel5.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel5["selection"]["points"][0]["location"])

    with col5_right:
        curr = st.session_state["active_tract"]
        st.markdown(f"<h3>Local Anchors: {curr}</h3>", unsafe_allow_html=True)
        st.markdown("<div class='side-pane-container'>", unsafe_allow_html=True)
        if curr in tract_centers:
            t_lon, t_lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(20).iterrows():
                st.markdown(f"<div class='anchor-pill'><b>{a['Name']}</b><br><span style='color:#4ade80; font-size:0.75rem;'>{a.get('Type', 'Anchor')} • {a['dist']:.1f} miles</span></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 6: RECOMMENDATION TOOL (DATA MAPPED TO EXACT HEADERS) ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendation</div></div>", unsafe_allow_html=True)
    col6_map, col6_data = st.columns([6, 4])
    
    with col6_map:
        fig6 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        fig6.update_layout(mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                           margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=750, clickmode='event+select')
        sel6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="map_v6_sync")
        if sel6 and sel6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel6["selection"]["points"][0]["location"])

    with col6_data:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"""
            <div style='background:#111827; padding:20px; border-radius:10px; border-left: 5px solid #4ade80; margin-bottom:20px;'>
                <span style='color:#94a3b8; font-size:0.8rem; font-weight:800;'>SELECTED TRACT</span>
                <h2 style='margin:0;'>{st.session_state["active_tract"]}</h2>
                <p style='color:#4ade80; font-weight:700; margin:0;'>{str(d.get('Parish', 'PARISH')).upper()} | {str(d.get('Region', 'REGION')).upper()}</p>
            </div>""", unsafe_allow_html=True)
            
            # Metro / Rural Classification
            c1, c2 = st.columns(2)
            m_status = str(d.get('Metro Status (Metropolitan/Rural)', '')).lower()
            with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if 'metropolitan' in m_status else 'NO'}</div><div class='metric-label'>Urban (Metro)</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if 'rural' in m_status else 'NO'}</div><div class='metric-label'>Rural Tract</div></div>", unsafe_allow_html=True)
            
            # Socio-Economic Metrics mapped to exact headers
            m1, m2 = st.columns(2)
            with m1:
                pov = d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{pov}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
                unemp = d.get('Unemployment Rate (%)', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{unemp}%</div><div class='metric-label'>Unemployment Rate</div></div>", unsafe_allow_html=True)
            with m2:
                mfi = d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>${mfi}</div><div class='metric-label'>Median Family Income</div></div>", unsafe_allow_html=True)
                bb = d.get('Broadband Internet (%)', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{bb}%</div><div class='metric-label'>Broadband Access</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            cat = st.selectbox("Recommendation Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation", "Infrastructure Enhancement"])
            justification = st.text_area("Narrative Justification", placeholder="Explain why this tract should be prioritized...", height=120)
            if st.button("Log Recommendation", use_container_width=True, type="primary"):
                if "recommendation_log" not in st.session_state: st.session_state["recommendation_log"] = []
                st.session_state["recommendation_log"].append({
                    "Tract": st.session_state["active_tract"], "Parish": d.get('Parish'), "Category": cat, "Narrative": justification
                })
                st.success("Tract Recommendation Logged!")

    if "recommendation_log" in st.session_state and st.session_state["recommendation_log"]:
        st.dataframe(pd.DataFrame(st.session_state["recommendation_log"]), use_container_width=True, hide_index=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())