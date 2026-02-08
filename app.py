import streamlit as st
import pandas as pd
import plotly.express as px
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

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

# --- 1. AUTHENTICATION ---
def check_password():
    """Returns `True` if the user had the correct password."""

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
        # Apply styling specifically for the login page
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
            html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
            .login-container { max-width: 450px; margin: 100px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
            .login-title { font-family: 'Playfair Display', serif; font-size: 2.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 10px; }
            .login-subtitle { font-size: 0.8rem; color: #4ade80; font-weight: 800; text-transform: uppercase; letter-spacing: 0.2em; margin-bottom: 30px; }
            /* Styling inputs to match */
            div[data-baseweb="input"] { background-color: #1f2937 !important; border-radius: 8px !important; }
            input { color: white !important; }
            </style>
            <div class="login-container">
                <div class="login-subtitle">Secure Access</div>
                <div class="login-title">Louisiana OZ 2.0 Portal</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Center the login form using columns
        _, col_mid, _ = st.columns([1, 1, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Log In", on_click=password_entered, use_container_width=True, type="primary")
            
            if "password_correct" in st.session_state and not st.session_state["password_correct"]:
                st.error("😕 User not found or password incorrect")
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
        .narrative-text { font-size: 1.2rem; line-height: 1.8; color: #cbd5e1; max-width: 900px; }
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2.2rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.8rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }
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

        centers = {}
        if geojson:
            for feature in geojson['features']:
                geoid = str(feature['properties'].get('GEOID', feature.get('id')))
                geom = feature['geometry']
                c_coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
                coords_array = np.array(c_coords)
                centers[geoid] = [np.mean(coords_array[:, 0]), np.mean(coords_array[:, 1])]
            
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTION 1 ---
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div><div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, housing, and innovation in the communities that need it most.</div></div>""", unsafe_allow_html=True)

    # --- SECTION 2, 3, 4 (Summarized for clarity) ---
    for sec_num, title, content in [
        ("SECTION 2", "The OZ 2.0 Benefit Framework", "Strategic financial incentives."),
        ("SECTION 3", "Investment Justification", "Stability and ROI analysis."),
        ("SECTION 4", "Best Practices", "Insights from leading policy groups.")
    ]:
        st.markdown(f"<div class='content-section'><div class='section-num'>{sec_num}</div><div class='section-title'>{title}</div></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1: st.markdown("<div class='benefit-card'><h3>Strategic Pillar A</h3><p>Detailed analysis of localized economic drivers.</p></div>", unsafe_allow_html=True)
        with c2: st.markdown("<div class='benefit-card'><h3>Strategic Pillar B</h3><p>Leveraging state-level infrastructure upgrades.</p></div>", unsafe_allow_html=True)
        with c3: st.markdown("<div class='benefit-card'><h3>Strategic Pillar C</h3><p>Long-term tax exclusion and wealth creation.</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: RECOMMENDATION TOOL ---
    st.markdown("""
        <div class='content-section' style='border-bottom:none;'>
            <div class='section-num'>SECTION 5</div>
            <div class='section-title'>Opportunity Zones 2.0 Recommendation Tool</div>
        </div>
    """, unsafe_allow_html=True)
    
    if "recommendation_log" not in st.session_state:
        st.session_state["recommendation_log"] = []

    if gj:
        m_col, p_col = st.columns([7, 3])
        with m_col:
            fig = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.2)"},
                mapbox_style="carto-darkmatter", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
            )
            fig.update_layout(coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=600)
            selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
        
        with p_col:
            current_id = "22071001700" 
            if selection and selection.get("selection", {}).get("points"):
                current_id = str(selection["selection"]["points"][0]["location"])
            
            row = master_df[master_df["geoid_str"] == current_id]
            if not row.empty:
                d = row.iloc[0]
                pov_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
                pov_display = pd.to_numeric(d.get(pov_col, 0), errors='coerce')
                pov_display = 0 if np.isnan(pov_display) else pov_display
                
                st.markdown(f"### Tract {current_id}")
                st.markdown(f"<p style='color:#4ade80; font-weight:800; font-size:1.2rem;'>{str(d.get('Parish', 'LOUISIANA')).upper()} ({str(d.get('Region', 'N/A')).upper()})</p>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{pov_display}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
                
                justification = st.text_area("Narrative Input", label_visibility="collapsed", placeholder="Justification...", height=150)
                if st.button("Log Recommendation", use_container_width=True, type="primary"):
                    if justification and current_id not in st.session_state["recommendation_log"]:
                        st.session_state["recommendation_log"].append(current_id)
                        st.rerun()

        st.write("---")
        st.markdown("### OZ 2.0 Recommendations")
        if st.session_state["recommendation_log"]:
            log_df = pd.DataFrame({
                "Recommendation Number": [str(i+1) for i in range(len(st.session_state["recommendation_log"]))],
                "Tract Number": [str(x) for x in st.session_state["recommendation_log"]]
            })
            st.dataframe(log_df, use_container_width=True, hide_index=True, column_config={
                "Recommendation Number": st.column_config.TextColumn("Recommendation Number", width="medium"),
                "Tract Number": st.column_config.TextColumn("Tract Number", width="large")
            })
            if st.button("Delete Selected"):
                st.session_state["recommendation_log"] = [] # Example logic
                st.rerun()
    
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())