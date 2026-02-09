import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import numpy as np
import ssl
from streamlit_gsheets import GSheetsConnection

# 0. INITIAL CONFIG
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Force SSL Bypass for Cloud Environments (Prevents GeoJSON fetch errors)
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. AUTHENTICATION ---
# (Keeping your working auth logic here...)
def check_password():
    if "password_correct" not in st.session_state:
        st.markdown("<div style='text-align:center; padding-top:100px;'><h1>OZ 2.0 Portal</h1></div>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login"):
                if u == "admin" and p == "louisiana2026": # Simplified for debug
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Invalid credentials")
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
        .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; color: #f8fafc; }
        .benefit-card { background: #161b28; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; margin-bottom: 10px; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #4ade80; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2.2rem; font-weight: 900; color: #4ade80; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE (With Troubleshooting Checks) ---
    @st.cache_data(ttl=3600)
    def load_all_data():
        # Fetch GeoJSON
        gj_data = None
        try:
            geo_url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
            r = requests.get(geo_url, timeout=5)
            gj_data = r.json()
        except Exception as e:
            st.warning(f"Map Geometry failed to load: {e}")

        # Helper for CSVs
        def safe_read(path):
            if os.path.exists(path):
                return pd.read_csv(path)
            st.error(f"File Not Found: {path}")
            return pd.DataFrame()

        # Load Master File
        master = safe_read("Opportunity Zones 2.0 - Master Data File.csv")
        if not master.empty:
            master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
            master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
                lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
            )

        # Load Anchors
        anchors = safe_read("la_anchors.csv")
        if not anchors.empty:
            anchors['Lat'] = pd.to_numeric(anchors['Lat'], errors='coerce')
            anchors['Lon'] = pd.to_numeric(anchors['Lon'], errors='coerce')
            anchors = anchors.dropna(subset=['Lat', 'Lon'])
        
        return gj_data, master, anchors

    import os
    gj, master_df, anchors_df = load_all_data()

    # --- SECTIONS 1-4 (Your Content) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div></div>", unsafe_allow_html=True)
    # ... (Include your HTML for sections 2, 3, 4 here) ...

    # --- SECTION 5: ASSET MAP ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Industrial & Institutional Assets</div></div>", unsafe_allow_html=True)
    
    if gj and not master_df.empty:
        fig_a = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", 
            color_discrete_map={"Eligible": "rgba(74, 222, 128, 0.3)", "Ineligible": "rgba(255,255,255,0.05)"},
            mapbox_style="carto-darkmatter", zoom=6, center={"lat": 31.0, "lon": -92.0}, opacity=0.4
        )
        if not anchors_df.empty:
            fig_a.add_trace(go.Scattermapbox(
                lat=anchors_df['Lat'], lon=anchors_df['Lon'], mode='markers',
                marker=go.scattermapbox.Marker(size=10, color='#4ade80'),
                text=anchors_df['Name'], hoverinfo='text'
            ))
        fig_a.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=600)
        st.plotly_chart(fig_a, use_container_width=True, key="map_assets_static")
    else:
        st.info("Map A is waiting for data...")

    # --- SECTION 6: RECOMMENDATION TOOL ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Tool</div></div>", unsafe_allow_html=True)
    
    if gj and not master_df.empty:
        m_col, p_col = st.columns([7, 3])
        with m_col:
            fig_b = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                color="Eligibility_Status", 
                color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                mapbox_style="carto-darkmatter", zoom=6, center={"lat": 31.0, "lon": -92.0}, opacity=0.8
            )
            fig_b.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False)
            selection = st.plotly_chart(fig_b, use_container_width=True, on_select="rerun", key="map_rec_interactive")
        
        with p_col:
            # Selection Logic
            current_id = "22071001700" 
            if selection and selection.get("selection", {}).get("points"):
                current_id = str(selection["selection"]["points"][0]["location"])
            
            st.subheader(f"Tract: {current_id}")
            # ... (Rest of your Side Panel Metric Logic) ...
    else:
        st.info("Map B is waiting for data...")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())