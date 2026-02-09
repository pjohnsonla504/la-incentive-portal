import streamlit as st
import pandas as pd
import plotly.express as px
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

# --- 0. INITIAL CONFIG & ERROR PREVENTION ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0", layout="wide")

# Pre-define selection variables to prevent NameError
selection5 = None
selection6 = None

# Global state for the selected tract
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 

# Force SSL Bypass for other data fetches
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. DATA ENGINE (LOCAL FILE FOCUS) ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon, dlat = lon2 - lon1, lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    return 3956 * 2 * asin(sqrt(a))

@st.cache_data(ttl=3600)
def load_assets():
    geojson = None
    # PATH: Updated to your specific filename in the repo
    local_geo = "tl_2025_22_tract.json"
    
    if os.path.exists(local_geo):
        with open(local_geo, "r") as f:
            geojson = json.load(f)
    
    def read_csv_safe(f):
        try: return pd.read_csv(f, encoding='utf-8')
        except: return pd.read_csv(f, encoding='latin1')

    # Load CSVs (from your Opportunity Zones Master File and LA anchors CSV)
    master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
    master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
    
    # Track OZ 2.0 Eligibility (Green = Eligible)
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
        # Note: Depending on TIGER files, the key might be 'GEOID' or 'GEOID20'
        # We try to find the best match for your 11-digit FIPs
        for feature in geojson['features']:
            props = feature['properties']
            geoid = props.get('GEOID') or props.get('GEOID20') or props.get('geoid')
            geom = feature['geometry']
            try:
                coords = np.array(geom['coordinates'][0]) if geom['type'] == 'Polygon' else np.array(geom['coordinates'][0][0])
                centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            except: continue
    return geojson, master, anchors, centers

gj, master_df, anchors_df, tract_centers = load_assets()

# --- 2. AUTHENTICATION ---
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

    # --- 3. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 2rem; font-weight: 900; color: #4ade80; }
        .anchor-pill { background: rgba(74, 222, 128, 0.1); border: 1px solid #4ade80; padding: 8px 12px; border-radius: 20px; margin-bottom: 8px; font-size: 0.85rem; }
        </style>
        """, unsafe_allow_html=True)

    # --- SECTION 5: STRATEGIC SELECTION TOOL ---
    st.markdown("<div class='content-section'><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

    m_col5, p_col5 = st.columns([6, 4])
    
    with m_col5:
        if gj:
            fig5 = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", 
                featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                color="map_color", color_discrete_map={1: "#4ade80", 0: "#1e293b"},
                mapbox_style="white-bg", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
            )
            fig5.update_layout(
                mapbox_layers=[{
                    "below": 'traces', "sourcetype": "raster",
                    "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]
                }],
                margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650
            )
            selection5 = st.plotly_chart(fig5, use_container_width=True, on_select="rerun", key="strat_map_v5")
            
            if selection5 and selection5.get("selection", {}).get("points"):
                st.session_state["active_tract"] = str(selection5["selection"]["points"][0]["location"])
        else:
            st.error(f"GeoJSON file 'tl_2025_22_tract.json' not found in repo.")
            st.session_state["active_tract"] = st.selectbox("Select Tract Manually", sorted(master_df['geoid_str'].unique()))

    with p_col5:
        current_id5 = st.session_state["active_tract"]
        row5 = master_df[master_df["geoid_str"] == current_id5]
        
        if not row5.empty:
            d5 = row5.iloc[0]
            st.markdown(f"<h2>Tract {current_id5}</h2><p style='color:#4ade80; font-weight:800;'>{str(d5.get('Parish', 'LOUISIANA')).upper()}</p>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1: 
                pov_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d5.get(pov_col, 'N/A')}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            with c2: 
                status5 = "ELIGIBLE" if d5['map_color'] == 1 else "INELIGIBLE"
                st.markdown(f"<div class='metric-card'><div class='metric-value' style='font-size:1.4rem;'>{status5}</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

            if not anchors_df.empty and current_id5 in tract_centers:
                t_lon, t_lat = tract_centers[current_id5]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                st.markdown("<br><p style='font-weight:bold; color:#94a3b8;'>NEAREST LOCAL ANCHORS</p>", unsafe_allow_html=True)
                for _, a in anchors_df.sort_values('dist').head(5).iterrows():
                    st.markdown(f"<div class='anchor-pill'>✔ {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)

    # --- SECTION 6: RECOMMENDATION TOOL ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-title'>Recommendation Log</div></div>", unsafe_allow_html=True)
    
    if "recommendation_log" not in st.session_state:
        st.session_state["recommendation_log"] = []

    m_col6, p_col6 = st.columns([7, 3])
    with m_col6:
        if gj:
            fig6 = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", 
                featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.2)"},
                mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
            )
            fig6.update_layout(
                mapbox_layers=[{
                    "below": 'traces', "sourcetype": "raster",
                    "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]
                }],
                coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=500
            )
            selection6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="rec_map_v6")
            if selection6 and selection6.get("selection", {}).get("points"):
                st.session_state["active_tract"] = str(selection6["selection"]["points"][0]["location"])

    with p_col6:
        current_id6 = st.session_state["active_tract"]
        st.markdown(f"### Log Tract {current_id6}")
        justification = st.text_area("Narrative Input", placeholder="Why this tract?", height=150, key="narr_input_6")
        if st.button("Log Recommendation", use_container_width=True, type="primary"):
            if current_id6 not in st.session_state["recommendation_log"]:
                st.session_state["recommendation_log"].append(current_id6)
                st.rerun()

    if st.session_state["recommendation_log"]:
        st.write("---")
        st.dataframe(pd.DataFrame({"Recommended Tracts": st.session_state["recommendation_log"]}), use_container_width=True, hide_index=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())