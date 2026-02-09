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
import streamlit.components.v1 as components
from datetime import datetime

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. AUTHENTICATION & CONNECTIONS ---
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
            .login-box { max-width: 450px; margin: 80px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
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
    conn = st.connection("gsheets", type=GSheetsConnection)

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; }
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        
        .metric-card { background: #111827; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 90px; display: flex; flex-direction: column; justify-content: center; }
        .metric-value { font-size: 1.2rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 4px; }
        
        /* Form Label and Input Styling */
        .stSelectbox label, .stTextArea label { color: #ffffff !important; font-weight: 700 !important; }
        .stTextArea textarea { color: #ffffff !important; background-color: #111827 !important; border: 1px solid #1e293b !important; }
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

    # --- SECTIONS 1-4 (PRESERVED) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><h1 style='color:white;'>Louisiana OZ 2.0 Portal</h1></div>", unsafe_allow_html=True)
    # (Sections 2-4 logic remains here)

    # --- SECTION 5: STRATEGIC ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    col5_map, col5_list = st.columns([0.6, 0.4], gap="large")
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
        list_items = ""
        if curr in tract_centers:
            t_lon, t_lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(25).iterrows():
                list_items += f"<div style='background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; font-family: sans-serif;'><div style='color:#4ade80; font-size:0.7rem; font-weight:900; text-transform:uppercase;'>{str(a.get('Type','')).upper()}</div><div style='font-weight:700; font-size:1rem; color:#f8fafc; margin-top:4px;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.8rem; margin-top:4px;'>📍 {a['dist']:.1f} miles</div></div>"
        components.html(f"""<div style="height: 580px; overflow-y: auto; padding-right: 10px; scrollbar-width: thin; scrollbar-color: #4ade80 #0b0f19;">{list_items}</div><style>::-webkit-scrollbar {{ width: 6px; }} ::-webkit-scrollbar-thumb {{ background: #4ade80; border-radius: 10px; }}</style>""", height=600)

    # --- SECTION 6: TRACT PROFILING & LIVE RECOMMENDATIONS ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendation</div>", unsafe_allow_html=True)
    col6_map, col6_data = st.columns([0.5, 0.5])
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
            st.markdown(f"<div style='background:#111827; padding:20px; border-radius:10px; border-left: 5px solid #4ade80; margin-bottom:20px;'><h2 style='margin:0;'>{st.session_state['active_tract']}</h2><p style='color:#4ade80; font-weight:700;'>{str(d.get('Parish','')).upper()} | {str(d.get('Region','')).upper()}</p></div>", unsafe_allow_html=True)
            
            # Metric Card Grid
            c1, c2, c3, c4 = st.columns(4)
            m_status = str(d.get('Metro Status (Metropolitan/Rural)', '')).lower()
            with c1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if 'metropolitan' in m_status else 'NO'}</div><div class='metric-label'>Urban</div></div>", unsafe_allow_html=True)
            with c2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if 'rural' in m_status else 'NO'}</div><div class='metric-label'>Rural</div></div>", unsafe_allow_html=True)
            with c3: 
                n_el = "YES" if str(d.get('NMTC Eligibility', '')).lower() in ['eligible','yes'] else "NO"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{n_el}</div><div class='metric-label'>NMTC</div></div>", unsafe_allow_html=True)
            with c4:
                n_dd = "YES" if str(d.get('NMTC Deeply Distressed', '')).lower() in ['eligible','yes'] else "NO"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{n_dd}</div><div class='metric-label'>NMTC DD</div></div>", unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            with m1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            with m2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined','0')}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            with m3: st.markdown(f"<div class='metric-card'><div class='metric-value'>${d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)','0')}</div><div class='metric-label'>Income</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            cat = st.selectbox("Justification Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification", height=100)
            if st.button("Submit Official Recommendation", use_container_width=True, type="primary"):
                new_data = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": st.session_state["active_tract"], "Category": cat, "Justification": just, "Is_Eligible": d['Eligibility_Status'], "User": st.session_state.get("username", "Unknown"), "Document": "N/A"}])
                conn.create(data=new_data)
                st.success("Recommendation successfully pushed to Google Sheets.")

    # --- BOTTOM SECTION: RECOMMENDATION TABLE ---
    st.markdown("### User Recommendations Dashboard")
    try:
        recs_df = conn.read(ttl="10s")
        st.dataframe(recs_df, use_container_width=True)
    except:
        st.info("Awaiting initial recommendations from Google Sheets.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())