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
            .login-box { max-width: 450px; margin: 80px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
            .login-title { font-family: 'Playfair Display', serif; font-size: 2.2rem; font-weight: 900; color: #f8fafc; }
            .login-subtitle { font-size: 0.8rem; color: #4ade80; font-weight: 800; text-transform: uppercase; letter-spacing: 0.2em; }
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
    st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2rem; font-weight: 900; color: #4ade80; }
        .anchor-pill { background: rgba(74, 222, 128, 0.1); border: 1px solid #4ade80; padding: 8px 12px; border-radius: 20px; margin-bottom: 8px; font-size: 0.9rem; color: #f8fafc; }
        .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
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
        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        
        # Format Headers
        anchors['Lat'] = pd.to_numeric(anchors['Lat'], errors='coerce')
        anchors['Lon'] = pd.to_numeric(anchors['Lon'], errors='coerce')
        anchors = anchors.dropna(subset=['Lat', 'Lon'])

        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        # Assign map_color for your logic (1 = Eligible Green, 0 = Ineligible Dark)
        master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).strip().lower() in ['eligible', 'yes', '1'] else 0)
        
        geojson = None
        try:
            r = requests.get("https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json", timeout=10)
            if r.status_code == 200: geojson = r.json()
        except: pass

        centers = {}
        if geojson:
            for feature in geojson['features']:
                geoid = feature['properties'].get('GEOID')
                geom = feature['geometry']
                if geom['type'] == 'Polygon': coords = np.array(geom['coordinates'][0])
                else: coords = np.array(geom['coordinates'][0][0])
                centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]

        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTIONS 1-4 (Intro Content) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='section-title'>Louisiana Opportunity Zone 2.0</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>Benefit Framework</div></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Advocacy & Readiness</div></div>", unsafe_allow_html=True)
    
    # --- SECTION 4: STRATEGIC TOOL (Per User Request) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

    m_col, p_col = st.columns([6, 4])
    with m_col:
        if gj:
            # Using mapbox for better detail and background control
            fig = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                color="map_color", 
                color_discrete_map={1: "#4ade80", 0: "rgba(30, 41, 59, 0.4)"},
                mapbox_style="carto-darkmatter", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=700)
            selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="strat_map")
        else:
            st.warning("🗺️ Map unavailable. Using manual selector.")
            target_geoid = st.selectbox("Select Tract ID", master_df['geoid_str'].unique())
            selection = None

    with p_col:
        current_id = "22071001700" 
        if selection and selection.get("selection", {}).get("points"):
            current_id = str(selection["selection"]["points"][0]["location"])
        
        row = master_df[master_df["geoid_str"] == current_id]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<h2>Tract {current_id}</h2><p style='color:#4ade80; font-weight:800; font-size:1.3rem;'>{str(d.get('Parish', 'LOUISIANA')).upper()}</p>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1: 
                pov_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
                pov = d.get(pov_col, 'N/A')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{pov}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            with c2: 
                status = "ELIGIBLE" if d['map_color'] == 1 else "INELIGIBLE"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{status}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

            # Proximity Analysis
            if not anchors_df.empty and current_id in tract_centers:
                t_lon, t_lat = tract_centers[current_id]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                st.markdown("<br><p style='font-size:0.8rem; font-weight:bold; color:#94a3b8; letter-spacing:0.1em;'>NEAREST LOCAL ANCHORS</p>", unsafe_allow_html=True)
                for _, a in anchors_df.sort_values('dist').head(6).iterrows():
                    st.markdown(f"<div class='anchor-pill'>✔ {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)

    # --- SECTION 6: RECOMMENDATION TOOL ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Recommendation Log</div></div>", unsafe_allow_html=True)
    if "recommendation_log" not in st.session_state:
        st.session_state["recommendation_log"] = []
    
    # Simple Narrative Logic
    rec_text = st.text_area("Add Justification for selected tract", placeholder="Enter notes here...")
    if st.button("Log Selection"):
        if current_id not in st.session_state["recommendation_log"]:
            st.session_state["recommendation_log"].append(current_id)
            st.rerun()
    
    st.write(st.session_state["recommendation_log"])

    st.sidebar.button("Log Out", on_click=lambda: st.session_state.clear())