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
            .stApp { background-color: #0b0f19; }
            .login-box { max-width: 450px; margin: 80px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
            .login-title { font-family: serif; font-size: 2.2rem; color: #f8fafc; }
            .login-subtitle { color: #4ade80; font-weight: 800; text-transform: uppercase; letter-spacing: 0.2em; }
            </style>
            <div class="login-box">
                <div class="login-subtitle">Louisiana OZ 2.0</div>
                <div class="login-title">Incentive Portal</div>
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
    st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")
    st.markdown("""
        <style>
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; }
        .benefit-card { background: #161b28; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; margin-bottom: 10px;}
        .metric-value { font-size: 2rem; font-weight: 900; color: #4ade80; }
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
        
        # Standardize anchor columns
        anchors['Lat'] = pd.to_numeric(anchors['Lat'], errors='coerce')
        anchors['Lon'] = pd.to_numeric(anchors['Lon'], errors='coerce')
        anchors = anchors.dropna(subset=['Lat', 'Lon'])

        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['Eligibility_Status'] = master[elig_col].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible')
        
        geojson = None
        geo_url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
        try:
            r = requests.get(geo_url, timeout=10, verify=False)
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
    st.markdown("<div class='content-section'><div class='section-title'>Louisiana OZ 2.0 Strategy</div></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAP ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 5</div>
            <div class='section-title'>Industrial & Institutional Asset Map</div>
            <p>Visualizing anchor assets (Name, Lat, Lon) against Opportunity Zone 2.0 eligibility.</p>
        </div>
    """, unsafe_allow_html=True)

    if gj:
        fig = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", 
            color_discrete_map={"Eligible": "#1e293b", "Ineligible": "rgba(15, 23, 42, 0.1)"},
            mapbox_style="carto-darkmatter", zoom=6.5, center={"lat": 31.0, "lon": -92.0}, opacity=0.5
        )

        fig.add_trace(go.Scattermapbox(
            lat=anchors_df['Lat'],
            lon=anchors_df['Lon'],
            mode='markers',
            marker=go.scattermapbox.Marker(size=10, color='#4ade80', opacity=0.9),
            text=anchors_df['Name'],
            hoverinfo='text',
            name='Economic Anchors'
        ))

        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=700, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

    # --- SECTION 6: PROXIMITY & RECOMMENDATION TOOL ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 6</div>
            <div class='section-title'>Proximity & Impact Analysis</div>
        </div>
    """, unsafe_allow_html=True)

    col_map, col_stats = st.columns([2, 1])

    with col_stats:
        target_tract = st.selectbox("Select Census Tract to Analyze Proximity", options=master_df['geoid_str'].unique())
        
        if target_tract in tract_centers:
            t_lon, t_lat = tract_centers[target_tract]
            
            # Distance logic using cleaned headers
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            nearby = anchors_df.sort_values('dist').head(3)
            
            st.markdown("#### Nearest Strategic Anchors")
            for _, anchor in nearby.iterrows():
                st.markdown(f"""
                    <div class='metric-card'>
                        <div class='metric-value'>{anchor['dist']:.1f} mi</div>
                        <div class='metric-label'>{anchor['Name']}</div>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.warning("Tract coordinates not found in spatial data.")

    with col_map:
        if target_tract in tract_centers:
            detail_fig = px.scatter_mapbox(
                nearby, lat="Lat", lon="Lon", text="Name",
                zoom=10, center={"lat": t_lat, "lon": t_lon}, height=500
            )
            detail_fig.update_layout(mapbox_style="carto-darkmatter", margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(detail_fig, use_container_width=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())