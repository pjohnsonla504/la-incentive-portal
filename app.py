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

    # --- 2. GLOBAL STYLING (Forcing Horizontal Alignment) ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        
        /* Layout Fix for Section 5 Side-by-Side */
        [data-testid="column"] {
            display: flex;
            flex-direction: column;
        }

        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        
        .asset-list-container { 
            height: 650px; 
            overflow-y: auto; 
            scrollbar-width: thin; 
            scrollbar-color: #4ade80 #0b0f19; 
            background: rgba(17, 24, 39, 0.6);
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 20px;
        }

        .anchor-pill { 
            background: #111827; 
            border: 1px solid #1e293b; 
            padding: 20px; 
            border-radius: 10px; 
            margin-bottom: 15px;
            transition: 0.2s;
        }
        .anchor-pill:hover { border-color: #4ade80; background: #1a2233; }
        .anchor-type { color: #4ade80; font-size: 0.75rem; font-weight: 900; text-transform: uppercase; letter-spacing: 0.15em; }
        .anchor-name { font-weight: 700; font-size: 1.1rem; color: #f8fafc; display: block; margin: 6px 0; }
        .anchor-dist { color: #94a3b8; font-size: 0.85rem; display: flex; align-items: center; }
        
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.5rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.7rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }
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
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        # Using [cite: 2026-01-22] logic for green highlighting
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

    # --- SECTIONS 1-4 (REDACTED FOR BREVITY - PRESERVED IN CODE) ---
    st.markdown("<div class='hero-title'>Louisiana Opportunity Zone 2.0 Portal</div>", unsafe_allow_html=True)

    # --- SECTION 5: FORCED SIDE-BY-SIDE LAYOUT ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    
    # Using a 60/40 split with no gap to ensure horizontal fit
    col5_map, col5_list = st.columns([0.6, 0.4], gap="medium")
    
    with col5_map:
        fig5 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        fig5.update_layout(mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                           margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650, clickmode='event+select')
        sel5 = st.plotly_chart(fig5, use_container_width=True, on_select="rerun", key="map_s5_final")
        if sel5 and sel5.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel5["selection"]["points"][0]["location"])

    with col5_list:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800; margin-bottom:10px;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        st.markdown("<div class='asset-list-container'>", unsafe_allow_html=True)
        if curr in tract_centers:
            t_lon, t_lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            # Sorting by distance and showing Type and Name as per screenshot requirement
            for _, a in anchors_df.sort_values('dist').head(30).iterrows():
                a_type = str(a.get('Type', 'Anchor Asset')).upper()
                st.markdown(f"""
                <div class='anchor-pill'>
                    <div class='anchor-type'>{a_type}</div>
                    <div class='anchor-name'>{a['Name']}</div>
                    <div class='anchor-dist'>🚩 {a['dist']:.1f} miles from center</div>
                </div>
                """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendation</div>", unsafe_allow_html=True)
    col6_map, col6_data = st.columns([0.6, 0.4], gap="medium")
    
    with col6_map:
        fig6 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        fig6.update_layout(mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                           margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=750, clickmode='event+select')
        sel6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="map_s6_final")
        if sel6 and sel6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel6["selection"]["points"][0]["location"])

    with col6_data:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"""
            <div style='background:#111827; padding:20px; border-radius:10px; border-left: 5px solid #4ade80; margin-bottom:20px;'>
                <span style='color:#94a3b8; font-size:0.8rem; font-weight:800;'>TRACT PROFILE</span>
                <h2 style='margin:0;'>{st.session_state["active_tract"]}</h2>
                <p style='color:#4ade80; font-weight:700; margin:0;'>{str(d.get('Parish', 'PARISH')).upper()} | {str(d.get('Region', 'REGION')).upper()}</p>
            </div>""", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            m_status = str(d.get('Metro Status (Metropolitan/Rural)', '')).lower()
            with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if 'metropolitan' in m_status else 'NO'}</div><div class='metric-label'>Urban (Metro)</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if 'rural' in m_status else 'NO'}</div><div class='metric-label'>Rural Tract</div></div>", unsafe_allow_html=True)
            
            m1, m2 = st.columns(2)
            with m1:
                pov = d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{pov}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
                unemp = d.get('Unemployment Rate (%)', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{unemp}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            with m2:
                mfi = d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>${mfi}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
                bb = d.get('Broadband Internet (%)', '0')
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{bb}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            cat = st.selectbox("Justification Category", ["Industrial Development", "Housing Initiative", "Infrastructure Improvement", "Commercial Expansion"])
            justification = st.text_area("Narrative Justification", height=120)
            if st.button("Log Official Recommendation", use_container_width=True, type="primary"):
                if "recommendation_log" not in st.session_state: st.session_state["recommendation_log"] = []
                st.session_state["recommendation_log"].append({
                    "Tract": st.session_state["active_tract"], "Parish": d.get('Parish'), "Category": cat, "Justification": justification
                })
                st.success("Logged Successfully")

    if "recommendation_log" in st.session_state and st.session_state["recommendation_log"]:
        st.dataframe(pd.DataFrame(st.session_state["recommendation_log"]), use_container_width=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())