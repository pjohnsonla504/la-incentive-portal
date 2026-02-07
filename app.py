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

    # --- 2. STYLING ---
    st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 4rem; font-weight: 900; line-height: 1.1; color: #f8fafc; margin-bottom: 10px; }
        .hero-subtitle { font-size: 1rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 30px; letter-spacing: 0.15em; }
        .narrative-text { font-size: 1.2rem; line-height: 1.7; color: #cbd5e1; max-width: 950px; }
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; transition: 0.3s ease; }
        .benefit-card:hover { border-color: #4ade80; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2rem; font-weight: 900; color: #4ade80; }
        .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; font-weight: 600; }
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
        # Primary 2025 Source, Fallback to alternate
        geo_urls = [
            "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json",
            "https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json"
        ]
        for url in geo_urls:
            try:
                r = requests.get(url, timeout=10)
                if r.status_code == 200:
                    geojson = r.json()
                    break
            except: continue

        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        
        # Clean FIPS - crucial for geoid matching
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
        # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).strip().lower() in ['eligible', 'yes', '1'] else 0)

        centers = {}
        if geojson:
            for feature in geojson['features']:
                geoid = str(feature['properties'].get('GEOID', feature.get('id')))
                geom = feature['geometry']
                coords = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
                centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTION 1: HERO ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div class='hero-subtitle'>Strategic Investment & Capital Deployment</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0</div>
            <div class='narrative-text'>
                Welcome to the official Opportunity Zone 2.0 Portal. This platform is designed to identify and justify 
                the most impactful investment opportunities across the state. By leveraging federal tax incentives 
                alongside Louisiana's unique industrial and educational anchors, we aim to bridge the capital gap 
                in underserved census tracts.
            </div>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTION 2: FRAMEWORK ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>30% Rural Step-Up</h3><p>Qualified Rural Opportunity Funds receive an enhanced 30% basis step-up, significantly increasing post-tax returns for projects outside major metropolitan hubs.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes on original capital gains through December 31, 2031, providing immediate liquidity for complex, long-term development phases.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Hold your investment for 10 years to pay <b>zero</b> federal capital gains tax on the appreciation of the new OZ 2.0 asset.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 3: STRATEGIC JUSTIFICATION ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Data-Driven Justification</div>", unsafe_allow_html=True)
    u1, u2 = st.columns(2)
    with u1: st.markdown("<div class='benefit-card' style='border-left: 5px solid #4ade80;'><h4>Healthcare & Institutional Hubs</h4><p>We target tracts adjacent to major medical and educational institutions, ensuring that new developments benefit from built-in foot traffic and workforce demand.</p></div>", unsafe_allow_html=True)
    with u2: st.markdown("<div class='benefit-card' style='border-left: 5px solid #4ade80;'><h4>Industrial Revitalization</h4><p>Focusing on Louisiana's port and corridor tracts to capitalize on the 30% rural incentive for manufacturing and logistics facilities.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 4: INTERACTIVE MAP ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Tract Selection Tool</div>", unsafe_allow_html=True)
    
    if gj:
        m_col, p_col = st.columns([7, 3])
        with m_col:
            id_key = "properties.GEOID" if "GEOID" in gj['features'][0]['properties'] else "id"
            fig = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey=id_key,
                color="map_color", color_discrete_map={1: "#4ade80", 0: "rgba(30,41,59,0.3)"},
                mapbox_style="carto-darkmatter", zoom=6.2, center={"lat": 31.0, "lon": -91.8},
                opacity=0.6
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=750)
            selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

        with p_col:
            current_id = "22071001700" # Default selector
            if selection and selection.get("selection", {}).get("points"):
                current_id = str(selection["selection"]["points"][0]["location"])
            
            row = master_df[master_df["geoid_str"] == current_id]
            if not row.empty:
                d = row.iloc[0]
                st.markdown(f"<h3>Tract {current_id}</h3><p style='color:#4ade80; font-weight:800; font-size:1.1rem;'>{d.get('Parish', 'Louisiana').upper()} PARISH</p>", unsafe_allow_html=True)
                
                # Metrics from Master CSV
                m1, m2 = st.columns(2)
                with m1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if d['map_color']==1 else 'NO'}</div><div class='metric-label'>OZ 2.0 Eligible</div></div>", unsafe_allow_html=True)

                if not anchors_df.empty and current_id in tract_centers:
                    t_lon, t_lat = tract_centers[current_id]
                    anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                    st.markdown("<br><p style='font-size:0.8rem; font-weight:900; color:#94a3b8; letter-spacing:0.1em;'>LOCAL ANCHORS</p>", unsafe_allow_html=True)
                    for _, a in anchors_df.sort_values('dist').head(6).iterrows():
                        st.markdown(f"<div class='anchor-pill'>✔ {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)
            else:
                st.info("👈 Click a tract on the map to analyze eligibility and proximity metrics.")
    else:
        st.error("⚠️ Map Layer Error: Could not reach the GeoJSON server. Please refresh the page.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())