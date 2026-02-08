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
        .hero-title { font-family: 'Playfair Display', serif; font-size: 4.2rem; font-weight: 900; line-height: 1.1; color: #f8fafc; margin-bottom: 15px; }
        .hero-subtitle { font-size: 1rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 30px; letter-spacing: 0.2em; }
        .narrative-text { font-size: 1.2rem; line-height: 1.8; color: #cbd5e1; max-width: 900px; }
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2.2rem; font-weight: 900; color: #4ade80; }
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
        
        # ELIGIBILITY: Tracks highlighted green are only those eligible for OZ 2.0
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
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div><div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, housing, and innovation in the communities that need it most. With a permanent, future-ready design, OZ 2.0 lets Louisiana compete nationally for capital while building inclusive growth that’s smart, strategic, and unmistakably Louisiana.</div></div>""", unsafe_allow_html=True)

    # --- SECTION 2 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes on original capital gains for 5 years.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Qualified taxpayer receives 10% basis step-up (30% if rural), following the 5-year deferral period.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Taxpayers that hold QOF investment for 10 years to pay zero federal capital gains tax on appreciation.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 3 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Investment Justification</div><div class='narrative-text'>Leveraging industrial anchors and institutional stability for long-term growth.</div></div>", unsafe_allow_html=True)
    
    # Syntax Fix Applied Here: New line before column assignment
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Industrial Stability</h3><p>Proximity to ports and manufacturing hubs ensures long-term tenant demand.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Workforce Pipeline</h3><p>Utilizing local educational anchors to provide a skilled labor force for new ventures.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Infrastructure ROI</h3><p>Targeting areas with planned state upgrades to maximize private capital impact.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


    # --- SECTION 4 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><div class='narrative-text'>Leveraging industrial anchors and institutional stability for long-term growth.</div></div>", unsafe_allow_html=True)
    
    # Syntax Fix Applied Here: New line before column assignment
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Industrial Stability</h3><p>Proximity to ports and manufacturing hubs ensures long-term tenant demand.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Workforce Pipeline</h3><p>Utilizing local educational anchors to provide a skilled labor force for new ventures.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Infrastructure ROI</h3><p>Targeting areas with planned state upgrades to maximize private capital impact.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
# --- SECTION 5: RECOMMENDATION TOOL (MAP & JUSTIFICATION) ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 5</div><div class='section-title'>Opportunity Zones 2.0 Recommendation Tool</div>", unsafe_allow_html=True)
    
    if gj:
        # Layout: Map on left, Analysis/Justification on right
        m_col, p_col = st.columns([7, 3])
        
        with m_col:
            # Map Rendering
            fig = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
                color="Eligibility_Status", 
                color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.2)"},
                mapbox_style="carto-darkmatter", zoom=6.2, center={"lat": 31.0, "lon": -91.8}, opacity=0.7
            )
            fig.update_layout(coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=800)
            fig.update_traces(marker_line_width=0.7, marker_line_color="#475569", showlegend=False)
            
            # Interactive Map Selection
            selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
        
        with p_col:
            # Determine which tract is selected
            current_id = "22071001700" # Default
            if selection and selection.get("selection", {}).get("points"):
                current_id = str(selection["selection"]["points"][0]["location"])
            
            row = master_df[master_df["geoid_str"] == current_id]
            if not row.empty:
                d = row.iloc[0]
                
                # 1. Selection Header & Parish Data
                st.markdown(f"### Tract {current_id}")
                st.markdown(f"<p style='color:#4ade80; font-weight:900;'>{d.get('Parish', 'Louisiana').upper()} PARISH</p>", unsafe_allow_html=True)
                
                # 2. Metric Card
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level', 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
                
                # 3. Anchor Proximity
                if not anchors_df.empty and current_id in tract_centers:
                    t_lon, t_lat = tract_centers[current_id]
                    anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                    st.write("---")
                    st.caption("NEAREST ANCHORS")
                    for _, a in anchors_df.sort_values('dist').head(3).iterrows():
                        st.write(f"📍 {a['Name']} ({a['dist']:.1f} mi)")
                
                st.write("---")
                
                # 4. Selection Progress Bar
                # (This could be tied to your GSheets 'Submitted' count in the future)
                st.caption("PORTAL SELECTION PROGRESS")
                st.progress(0.65) # Static 65% for visual demo
                
                # 5. Justification Box
                st.markdown("#### Recommendation Narrative")
                justification = st.text_area(
                    label="Justification Narrative",
                    label_visibility="collapsed",
                    placeholder=f"Explain why Tract {current_id} is a priority...",
                    height=150
                )
                
                if st.button("Submit Recommendation", use_container_width=True, type="primary"):
                    if justification:
                        st.success(f"Tract {current_id} submitted!")
                    else:
                        st.error("Please enter a justification.")
    else:
        st.error("⚠️ Map service offline.")
    
    st.markdown("</div>", unsafe_allow_html=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())