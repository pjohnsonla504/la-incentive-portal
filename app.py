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

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username"].strip()
            p = str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    return
            st.session_state["password_correct"] = False
        except Exception: st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("<h2 style='text-align:center; color:white; margin-top:100px;'>OZ 2.0 Secure Portal</h2>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; line-height: 1.1; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 220px; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 12px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 5px; }
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; border: 1px solid #1e293b; margin-bottom: 15px; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE (CORRECTED POLICYMAP CRITERIA) ---
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
        
        # Mapping official columns
        poverty_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
        unemployment_col = 'Unemployment Rate (%)'
        mfi_col = 'Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)'
        
        def clean_num(s):
            try: return float(str(s).replace('%','').replace('$','').replace(',','').strip())
            except: return 0.0

        master['_pov'] = master[poverty_col].apply(clean_num)
        master['_unemp'] = master[unemployment_col].apply(clean_num)
        master['_mfi'] = master[mfi_col].apply(clean_num)

        # PolicyMap / CDFI Benchmarks
        NAT_UNEMP = 5.3 
        STATE_MFI = 86934 

        # 1. NMTC ELIGIBLE (Standard Low Income Community)
        master['NMTC_Eligible'] = ((master['_pov'] >= 20) | (master['_mfi'] <= (0.8 * STATE_MFI))).map({True:'Yes', False:'No'})
        
        # 2. SEVERE DISTRESS (PolicyMap maroon/brown - 30% Poverty or 60% MFI)
        master['Severe_Distress'] = ((master['_pov'] >= 30) | (master['_mfi'] <= (0.6 * STATE_MFI)) | (master['_unemp'] >= (1.5 * NAT_UNEMP))).map({True:'Yes', False:'No'})
        
        # 3. DEEP DISTRESS (PolicyMap red - 40% Poverty or 40% MFI)
        master['Deep_Distress'] = ((master['_pov'] >= 40) | (master['_mfi'] <= (0.4 * STATE_MFI)) | (master['_unemp'] >= (2.5 * NAT_UNEMP))).map({True:'Yes', False:'No'})

        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).lower() in ['eligible','yes','1'] else 'Ineligible')
        
        anchors = read_csv_safe("la_anchors.csv")
        anchors['Link'] = anchors.get('Link', pd.Series([""]*len(anchors))).fillna("")
        
        centers = {}
        if geojson:
            for f in geojson['features']:
                gid = f['properties'].get('GEOID') or f['properties'].get('GEOID20')
                try:
                    c = np.array(f['geometry']['coordinates'][0]) if f['geometry']['type'] == 'Polygon' else np.array(f['geometry']['coordinates'][0][0])
                    centers[gid] = [np.mean(c[:, 0]), np.mean(c[:, 1])]
                except: pass
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map(df, height=600):
        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", 
                                     color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#334155"},
                                     mapbox_style="carto-positron", zoom=6, center={"lat": 30.8, "lon": -91.8}, opacity=0.5)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height)
        return fig

    # --- SECTION 5: ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div></div>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([0.6, 0.4], gap="large")
    with col_a:
        st.plotly_chart(render_map(master_df), use_container_width=True, on_select="rerun", key="map_main")
        if st.session_state.get("map_main") and st.session_state["map_main"]["selection"]["points"]:
            st.session_state["active_tract"] = str(st.session_state["map_main"]["selection"]["points"][0]["location"])

    with col_b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>LOCAL ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        list_html = ""
        if curr in tract_centers:
            lon, lat = tract_centers[curr]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(10).iterrows():
                btn = f"<div style='margin-top:8px;'><a href='{a['Link']}' target='_blank' style='background:#4ade80; color:#0b0f19; padding:4px 10px; border-radius:4px; font-size:0.7rem; font-weight:900; text-decoration:none;'>VIEW SITE 🔗</a></div>" if a['Type'] in ['Land','Buildings'] and a['Link'] else ""
                list_html += f"<div style='background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px;'><div style='color:#4ade80; font-size:0.6rem; font-weight:900;'>{str(a['Type']).upper()}</div><div style='font-weight:700; color:white;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.7rem;'>📍 {a['dist']:.1f} miles away</div>{btn}</div>"
        components.html(f"<div style='height:500px; overflow-y:auto; font-family:sans-serif;'>{list_html}</div>", height=520)

    # --- SECTION 6: CORRECTED METRICS ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling</div></div>", unsafe_allow_html=True)
    row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
    if not row.empty:
        d = row.iloc[0]
        st.markdown(f"<div class='tract-header-container'><div style='font-size:1.8rem; font-weight:900; color:#4ade80;'>{str(d.get('Parish','')).upper()}</div><div>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
        
        m_cols = st.columns(4)
        # PolicyMap Core Indicators
        metrics = [
            (d['NMTC_Eligible'], "NMTC Eligible"),
            (d['Severe_Distress'], "Severe Distress"),
            (d['Deep_Distress'], "Deep Distress (High)"),
            (f"{d['_pov']:.1f}%", "Poverty Rate"),
            (f"{d['_unemp']:.1f}%", "Unemployment"),
            (f"${d['_mfi']:,.0f}", "Median Income"),
            (d.get('Broadband Internet (%)','0%'), "Broadband"),
            (d.get('Metro Status (Metropolitan/Rural)','N/A'), "Tract Status")
        ]
        for i, (val, lbl) in enumerate(metrics):
            m_cols[i % 4].markdown(f"<div class='metric-card'><div class='metric-value'>{val}</div><div class='metric-label'>{lbl}</div></div>", unsafe_allow_html=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())