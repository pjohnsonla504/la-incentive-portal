import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import numpy as np
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

# --- 1. AUTHENTICATION (Service Account) ---
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
                stored_password = str(user_row['password'].values[0]).strip()
                if entered_pass == stored_password:
                    st.session_state["password_correct"] = True
                    del st.session_state["password"]
                    del st.session_state["username"]
                else:
                    st.session_state["password_correct"] = False
            else:
                st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"⚠️ Security Error: {e}")
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("Louisiana OZ 2.0 Login")
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
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; margin: 0 auto; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }
        .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
        .narrative-text { font-size: 1.1rem; line-height: 1.6; color: #cbd5e1; margin-bottom: 25px; max-width: 1100px; }
        .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; transition: all 0.3s ease; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.6rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.65rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }
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
        # Stabilized GeoJSON Fetching
        url_geo = "https://raw.githubusercontent.com/OpenDataDE/State-zip-code-GeoJSON/master/la_louisiana_census_tracts.json"
        try:
            r = requests.get(url_geo, timeout=10)
            geojson = r.json()
        except:
            # Fallback to the other source if needed
            url_geo_alt = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
            geojson = requests.get(url_geo_alt).json()
            
        master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = pd.read_csv("la_anchors.csv")
        
        # KEY JOIN FIX
        master['geoid_str'] = master['11-digit FIP'].apply(lambda x: str(int(float(x))) if pd.notnull(x) else "").str.zfill(11)
        
        # ELIGIBILITY LOGIC
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).strip().lower() in ['eligible', 'yes', '1'] else 0)

        # Centroids
        centers = {}
        for feature in geojson['features']:
            geoid = feature['properties'].get('GEOID', feature['properties'].get('geoid'))
            geom = feature['geometry']
            # Get mean coordinates regardless of Polygon or MultiPolygon
            c_list = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
            coords = np.array(c_list)
            centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTIONS 1, 2, 3 (UNTOUCHED) ---
    st.markdown("<div class='content-section' style='padding-top:80px;'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Recommendation Portal</div><div class='narrative-text'>The Opportunity Zones program is a federal initiative designed to drive long-term private investment into distressed communities...</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Louisiana OZ 2.0 Framework</div></div>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1: st.markdown("<div class='benefit-card'><div class='benefit-label'>Benefit 01</div><div class='benefit-header'>5-Year Rolling Deferral</div><div class='benefit-body'>Investors can defer taxes on original capital gains through a 5-year rolling window...</div></div>", unsafe_allow_html=True)
    with b2: st.markdown("<div class='benefit-card'><div class='benefit-label'>Benefit 02</div><div class='benefit-header'>10% Urban / 30% Rural Step-Up</div><div class='benefit-body'>Standard QOFs receive a 10% basis step-up... Qualified Rural Funds (QROFs) receive an enhanced 30% basis step-up...</div></div>", unsafe_allow_html=True)
    with b3: st.markdown("<div class='benefit-card'><div class='benefit-label'>Benefit 03</div><div class='benefit-header'>Permanent Exclusion</div><div class='benefit-body'>Holding for 10 years results in zero federal capital gains tax on appreciation.</div></div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Opportunity Zone Justification Using Data</div></div>", unsafe_allow_html=True)
    uc1, uc2 = st.columns(2)
    with uc1: st.markdown("<div class='benefit-card' style='border-left: 5px solid #4ade80;'><div class='benefit-label'>Use-Case: Rural Healthcare</div><div class='benefit-body'><b>Objective: Modernize critical care.</b> Utilizing the 30% Rural Step-Up...</div></div>", unsafe_allow_html=True)
    with uc2: st.markdown("<div class='benefit-card' style='border-left: 5px solid #4ade80;'><div class='benefit-label'>Use-Case: Main Street Reuse</div><div class='benefit-body'><b>Objective: Historic Revitalization.</b> Driving investment into core commercial districts...</div></div>", unsafe_allow_html=True)

    # --- SECTION 4: MAP ---
    st.markdown("<div class='content-section' style='margin-top:40px;'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

    m_col, p_col = st.columns([6, 4])
    with m_col:
        # Check if the properties ID is 'GEOID' or 'geoid'
        id_key = "properties.GEOID" if "GEOID" in gj['features'][0]['properties'] else "properties.geoid"
        
        fig = px.choropleth(master_df, geojson=gj, locations="geoid_str", featureidkey=id_key,
                            color="map_color", color_discrete_map={1: "#4ade80", 0: "#1e293b"}, projection="mercator")
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=700)
        selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

    with p_col:
        target_geoid = "22071001700" 
        if selection and selection.get("selection", {}).get("points"):
            target_geoid = str(selection["selection"]["points"][0]["location"])
        
        row = master_df[master_df["geoid_str"] == target_geoid]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<h2>Tract {target_geoid}</h2><p style='color:#4ade80; font-weight:800;'>{str(d.get('Parish', 'LOUISIANA')).upper()}</p>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 'N/A')}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if d['map_color']==1 else 'NO'}</div><div class='metric-label'>Eligible</div></div>", unsafe_allow_html=True)

            if not anchors_df.empty and target_geoid in tract_centers:
                t_lon, t_lat = tract_centers[target_geoid]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                st.markdown("<br><p style='font-size:0.8rem; font-weight:bold; color:#94a3b8;'>NEAREST ANCHORS</p>", unsafe_allow_html=True)
                for _, a in anchors_df.sort_values('dist').head(6).iterrows():
                    st.markdown(f"<div class='anchor-pill'>✔ {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)
        else:
            st.info("Select a tract on the map to see details.")

    st.sidebar.button("Log Out", on_click=lambda: st.session_state.clear())