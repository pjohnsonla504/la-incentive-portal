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

# --- 0. INITIAL CONFIG & ERROR PREVENTION ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Pre-define selection variables to prevent NameError
selection5 = None
selection6 = None

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 

# Force SSL Bypass
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

    # --- 2. GLOBAL STYLING (Uniform Heights + Hover Green Border) ---
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
        
        /* UNIFORM INTERACTIVE BENEFIT CARDS */
        .benefit-card { 
            background: #161b28; 
            padding: 35px; 
            border: 1px solid #2d3748; 
            border-radius: 8px; 
            height: 100%;
            min-height: 280px; 
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
            transition: all 0.3s ease-in-out;
        }

        .benefit-card:hover {
            border: 1px solid #4ade80;
            transform: translateY(-5px);
            background: #1c2433;
            box-shadow: 0px 10px 20px rgba(74, 222, 128, 0.1);
        }
        
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2.2rem; font-weight: 900; color: #4ade80; }
        .anchor-pill { background: rgba(74, 222, 128, 0.1); border: 1px solid #4ade80; padding: 8px 12px; border-radius: 20px; margin-bottom: 8px; font-size: 0.9rem; color: #f8fafc; }
        
        /* Remove Streamlit blue metric bar if applicable */
        [data-testid="stMetric"] label { display: none; }
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
        local_geo = "tl_2025_22_tract.json"
        if os.path.exists(local_geo):
            with open(local_geo, "r") as f:
                geojson = json.load(f)

        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        master['map_color'] = master['Eligibility_Status'].apply(lambda x: 1 if x == 'Eligible' else 0)
        
        anchors = read_csv_safe("la_anchors.csv")
        anchors['Lat'] = pd.to_numeric(anchors['Lat'], errors='coerce')
        anchors['Lon'] = pd.to_numeric(anchors['Lon'], errors='coerce')
        anchors = anchors.dropna(subset=['Lat', 'Lon'])

        centers = {}
        if geojson:
            for feature in geojson['features']:
                props = feature['properties']
                geoid = props.get('GEOID') or props.get('GEOID20')
                geom = feature['geometry']
                try:
                    coords = np.array(geom['coordinates'][0]) if geom['type'] == 'Polygon' else np.array(geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTION 1 ---
    st.markdown("""<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Opportunity Zones 2.0</div><div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div><div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, housing, and innovation in the communities that need it most.</div></div>""", unsafe_allow_html=True)

    # --- SECTION 2 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The OZ 2.0 Benefit Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes on original capital gains for 5 years.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>Qualified taxpayer receives 10% basis step-up (30% if rural).</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Permanent Exclusion</h3><p>Zero federal capital gains tax on appreciation after 10 years.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 3 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Census Tract Advocacy</div><div class='narrative-text'>Regional driven advocacy to amplify local stakeholder needs.</div></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Geographically Disbursed</h3><p>Zones will be distributed throughout the state focusing on rural and investment ready tracts.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Distressed Communities</h3><p>Eligibility is dependent on the federal definition of a low-income community.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Project Ready</h3><p>Aligning regional recommendations with tracts likely to receive private investment.</p></div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 4 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Best Practices</div><div class='narrative-text'>Leverage OZ 2.0 capital to catalyze community and economic development.</div></div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>Economic Innovation Group</h3><p>Proximity to ports and manufacturing hubs ensures long-term tenant demand.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Frost Brown Todd</h3><p>Utilizing local educational anchors to provide a skilled labor force.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("""<div class='benefit-card'><h3>American Policy Institute</h3><p>Stack incentives to de-risk projects. Historic Tax Credits, New Markets Tax Credits, and LIHTC are available to Louisiana developers.</p></div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 5: STRATEGIC SELECTION TOOL (FIXED SCHEME & SELECTION) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

    m_col5, p_col5 = st.columns([6, 4])
    with m_col5:
        if gj:
            fig5 = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", 
                featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                color="Eligibility_Status", 
                color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                mapbox_style="white-bg", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.8
            )
            # Override blue highlight and vertical lines
            fig5.update_traces(
                selected={'marker': {'opacity': 1}},
                unselected={'marker': {'opacity': 0.4}},
                marker_line_width=0
            )
            fig5.update_layout(
                mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650,
                clickmode='event+select'
            )
            selection5 = st.plotly_chart(fig5, use_container_width=True, on_select="rerun", key="strat_map_fixed")
            if selection5 and selection5.get("selection", {}).get("points"):
                st.session_state["active_tract"] = str(selection5["selection"]["points"][0]["location"])
        else:
            st.error("GeoJSON not found locally.")

    with p_col5:
        current_id5 = st.session_state["active_tract"]
        row5 = master_df[master_df["geoid_str"] == current_id5]
        if not row5.empty:
            d5 = row5.iloc[0]
            st.markdown(f"<h2>Tract {current_id5}</h2><p style='color:#4ade80; font-weight:800;'>{str(d5.get('Parish', 'LOUISIANA')).upper()}</p>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1: 
                pk = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d5.get(pk, 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            with c2: 
                status = d5['Eligibility_Status'].upper()
                st.markdown(f"<div class='metric-card'><div class='metric-value' style='font-size:1.4rem;'>{status}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

            if not anchors_df.empty and current_id5 in tract_centers:
                t_lon, t_lat = tract_centers[current_id5]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                st.markdown("<br><p style='font-weight:bold; color:#94a3b8;'>NEAREST LOCAL ANCHORS</p>", unsafe_allow_html=True)
                for _, a in anchors_df.sort_values('dist').head(5).iterrows():
                    st.markdown(f"<div class='anchor-pill'>✔ {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)

    # --- SECTION 6: RECOMMENDATION TOOL ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 6</div><div class='section-title'>Opportunity Zones 2.0 Recommendation Tool</div></div>", unsafe_allow_html=True)
    if "recommendation_log" not in st.session_state:
        st.session_state["recommendation_log"] = []

    m_col6, p_col6 = st.columns([7, 3])
    with m_col6:
        if gj:
            fig6 = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", 
                featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                color="Eligibility_Status", 
                color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.8
            )
            fig6.update_traces(selected={'marker': {'opacity': 1}}, unselected={'marker': {'opacity': 0.4}}, marker_line_width=0)
            fig6.update_layout(
                mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=600,
                clickmode='event+select'
            )
            selection6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="rec_map_fixed")
            if selection6 and selection6.get("selection", {}).get("points"):
                st.session_state["active_tract"] = str(selection6["selection"]["points"][0]["location"])

    with p_col6:
        current_id6 = st.session_state["active_tract"]
        st.markdown(f"### Log Tract {current_id6}")
        justification = st.text_area("Narrative Input", placeholder="Why this tract?", height=150, key="narr_input_6")
        if st.button("Log Recommendation", use_container_width=True, type="primary"):
            if current_id6 not in [x['Tract'] for x in st.session_state["recommendation_log"]]:
                st.session_state["recommendation_log"].append({"Tract": current_id6, "Narrative": justification})
                st.rerun()

    if st.session_state["recommendation_log"]:
        st.write("---")
        st.dataframe(pd.DataFrame(st.session_state["recommendation_log"]), use_container_width=True, hide_index=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())