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

# --- 0. INITIAL CONFIG & STATE INITIALIZATION ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

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
                    st.session_state["current_user"] = u 
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            .stApp { background-color: #0b0f19; }
            .login-box { max-width: 450px; margin: 80px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
            .login-title { font-family: serif; font-size: 2.2rem; font-weight: 900; color: #f8fafc; }
            </style>
            <div class="login-box">
                <div class="login-title">Louisiana OZ 2.0 Portal</div>
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-family: serif; font-size: 4.2rem; font-weight: 900; line-height: 1.1; color: #f8fafc; margin-bottom: 15px; }
        .hero-subtitle { font-size: 1rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 30px; letter-spacing: 0.2em; }
        .benefit-card { background: #161b28; padding: 35px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; transition: 0.3s; }
        .metric-card { background: #111827; padding: 8px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 8px;}
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 3px; }
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

    # --- SECTIONS 1-4: VISION & FRAMEWORK ---
    st.markdown("<div class='content-section'><div class='hero-title'>Louisiana Opportunity Zone 2.0</div></div>", unsafe_allow_html=True)
    
    # --- SECTION 5: ASSET MAPPING (WHITE PARISH NAMES) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    col5_map, col5_list = st.columns([0.6, 0.4], gap="large")
    with col5_map:
        fig5 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        
        # Adding Dark Base with White Parish Labels
        fig5.update_layout(
            mapbox_layers=[
                {"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]},
            ],
            mapbox_style="dark", # Native Mapbox dark style supports high-vis labels
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=650, clickmode='event+select')
        
        sel5 = st.plotly_chart(fig5, use_container_width=True, on_select="rerun", key="map_s5_labels")
        if sel5 and sel5.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel5["selection"]["points"][0]["location"])

    with col5_list:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800; margin-bottom:10px;'>ANCHOR ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        list_items = ""
        if curr in tract_centers:
            t_lon, t_lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(25).iterrows():
                list_items += f"<div style='background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px;'><div style='color:#4ade80; font-size:0.7rem; font-weight:900;'>{str(a.get('Type','')).upper()}</div><div style='font-weight:700; color:#f8fafc;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.8rem;'>📍 {a['dist']:.1f} miles</div></div>"
        st.components.v1.html(f"""<div style="height: 580px; overflow-y: auto; padding-right: 10px;">{list_items}</div>""", height=600)

    # --- SECTION 6: TRACT PROFILING (WHITE PARISH NAMES) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling</div>", unsafe_allow_html=True)
    col6_map, col6_data = st.columns([0.5, 0.5])
    with col6_map:
        fig6 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        
        fig6.update_layout(
            mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
            mapbox_style="dark", # Switches to white labels automatically in Mapbox Dark
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=750, clickmode='event+select')
        
        sel6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="map_s6_labels")
        if sel6 and sel6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel6["selection"]["points"][0]["location"])

    with col6_data:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            poverty_rate = float(d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0))
            med_income = float(str(d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')).replace(',','').replace('$',''))
            
            st.markdown(f"### {st.session_state['active_tract']} | {str(d.get('Parish','')).upper()}")
            
            # Metric Rows
            g1, g2, g3 = st.columns(3)
            with g1:
                status_val = "URBAN" if "metropolitan" in str(d.get('Metro Status (Metropolitan/Rural)', '')).lower() else "RURAL"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{status_val}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            with g2:
                nmtc_elig = "YES" if (poverty_rate > 20 or med_income < 71200) else "NO"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{nmtc_elig}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            with g3:
                deeply_dist = "YES" if (poverty_rate > 40 or med_income < 35600) else "NO"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{deeply_dist}</div><div class='metric-label'>Deeply Distressed</div></div>", unsafe_allow_html=True)
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{poverty_rate}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Total!!Total population!!18 to 24 years','0')}</div><div class='metric-label'>Pop (18-24)</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Total!!Total population!!65 years and over','0')}</div><div class='metric-label'>Pop (65+)</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>${med_income:,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Broadband Internet (%)','0')}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)
            
            cat = st.selectbox("Justification Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification")
            if st.button("Submit Recommendation", type="primary", use_container_width=True):
                try:
                    new_rec = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": st.session_state["active_tract"], "Category": cat, "Justification": just, "User": st.session_state["current_user"]}])
                    conn.create(data=new_rec)
                    st.success("Recommendation Pushed.")
                except Exception as e: st.error(f"Error: {e}")

    # --- MY HISTORY ---
    st.markdown("### My Regional Recommendations")
    try:
        all_recs = conn.read(ttl="5s")
        my_recs = all_recs[all_recs['User'].astype(str) == st.session_state["current_user"]]
        st.dataframe(my_recs, use_container_width=True)
    except: st.info("No history found.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())