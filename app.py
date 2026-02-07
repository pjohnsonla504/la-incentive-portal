import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import numpy as np
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

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
        st.title("Louisiana OZ 2.0 Portal")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Log In", on_click=password_entered)
        return False
    return True

if check_password():

    # --- 2. DESIGN SYSTEM ---
    st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; letter-spacing: -0.02em; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 4rem; font-weight: 900; line-height: 1.1; margin-bottom: 20px; color: #f8fafc; }
        .hero-subtitle { font-size: 0.95rem; color: #4ade80; font-weight: 800; letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 30px; }
        .narrative-text { font-size: 1.2rem; line-height: 1.7; color: #cbd5e1; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; transition: 0.3s; }
        .benefit-card:hover { border-color: #4ade80; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
        .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA & ANALYTICS ---
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 3956 * 2 * asin(sqrt(a))

    @st.cache_data(ttl=3600)
    def load_assets():
        # Source 2025 Tract Data
        url_geo = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json" # Mapping to tl_2025 source logic
        try:
            r = requests.get(url_geo, timeout=10)
            geojson = r.json()
        except:
            st.error("GeoJSON Load Failed")
            return None, None, None, {}

        # Load CSVs
        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        
        # Clean FIPS & Match Eligibility
        master['geoid_str'] = master['11-digit FIP'].apply(lambda x: str(int(float(x))).zfill(11) if pd.notnull(x) else "")
        # Highlight green ONLY if eligible for OZ 2.0
        master['map_color'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 1 if str(x).lower() == 'eligible' else 0)

        centers = {}
        for feature in geojson['features']:
            geoid = feature['properties'].get('GEOID', feature['properties'].get('geoid'))
            geom = feature['geometry']
            coords = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
            centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTION 1: HERO ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div class='hero-subtitle'>The Next Frontier of Louisiana Investment</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Strategic Portal</div>
            <div class='narrative-text'>
                Building upon the foundational success of the 2017 Tax Cuts and Jobs Act, the OZ 2.0 framework 
                is designed to direct surgical capital into Louisiana's high-potential rural and urban tracts. 
                This portal provides the data-driven justification required for Institutional and Qualified 
                Opportunity Fund (QOF) deployment.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTION 2: FRAMEWORK ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>5-Year Deferral</h3><p>Defer capital gains taxes on original investments through 2031, providing immediate liquidity for complex Louisiana developments.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>30% Rural Step-Up</h3><p>Qualified Rural Opportunity Funds (QROFs) receive a significant 30% basis step-up, incentivizing investment in parishes outside major metros.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Eliminate 100% of federal capital gains tax on the appreciation of the OZ 2.0 investment after a 10-year holding period.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 3: USE CASES ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Use Cases</div>", unsafe_allow_html=True)
    u1, u2 = st.columns(2)
    with u1: st.markdown("<div class='benefit-card' style='border-left: 4px solid #4ade80;'><h4>Rural Infrastructure & Health</h4><p>Deploying capital into Level III Trauma Centers and broadband infrastructure within eligible rural tracts to secure the 30% basis step-up.</p></div>", unsafe_allow_html=True)
    with u2: st.markdown("<div class='benefit-card' style='border-left: 4px solid #4ade80;'><h4>Urban Workforce Housing</h4><p>Utilizing proximity to anchors like LSU and Tulane to develop multi-family housing in federally designated census tracts.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 4: THE MAP TOOL ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 4</div><div class='section-title'>Interactive Tract Analysis</div>", unsafe_allow_html=True)
    
    m_col, p_col = st.columns([7, 3])
    
    with m_col:
        # MAPBOX / LEAFLET STYLE LAYER
        fig = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="map_color", color_discrete_map={1: "#4ade80", 0: "rgba(30, 41, 59, 0.5)"},
            mapbox_style="carto-darkmatter", zoom=6.2, 
            center={"lat": 31.0, "lon": -91.8}, opacity=0.7
        )
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=750)
        selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

    with p_col:
        current_id = "22071001700"
        if selection and selection.get("selection", {}).get("points"):
            current_id = str(selection["selection"]["points"][0]["location"])
        
        row = master_df[master_df["geoid_str"] == current_id]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<h3>Tract {current_id}</h3><p style='color:#4ade80; font-weight:800; text-transform:uppercase;'>{d['Parish']} Parish</p>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if d['map_color']==1 else 'NO'}</div><div class='metric-label'>OZ 2.0 Eligible</div></div>", unsafe_allow_html=True)

            if not anchors_df.empty and current_id in tract_centers:
                t_lon, t_lat = tract_centers[current_id]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                st.markdown("<br><p style='font-size:0.75rem; font-weight:900; color:#94a3b8; letter-spacing:0.1em;'>STRATEGIC ANCHORS</p>", unsafe_allow_html=True)
                for _, a in anchors_df.sort_values('dist').head(5).iterrows():
                    st.markdown(f"<div class='anchor-pill'>📍 {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)
        else:
            st.info("Select a census tract on the map to view data metrics.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())