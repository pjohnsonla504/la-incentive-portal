import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import json
import os
import numpy as np
import ssl
from streamlit_gsheets import GSheetsConnection

# 0. INITIAL CONFIG
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

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
            u, p = st.session_state["username"].strip(), str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if "password_correct" not in st.session_state:
        st.markdown("<h2 style='text-align:center; color:white; margin-top:50px;'>Louisiana OZ 2.0 Login</h2>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Secure Login", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 25px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.7rem; font-weight: 900; color: #4ade80; margin-bottom: 2px; letter-spacing: 0.1em; }
        .section-title { font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; }
        .narrative-text { font-size: 1.1rem; line-height: 1.5; color: #cbd5e1; margin-bottom: 15px; }
        .benefit-card { background: #161b28; padding: 20px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
        .asset-list-item { font-size: 0.85rem; padding: 6px; border-bottom: 1px solid #1e293b; color: #94a3b8; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    @st.cache_data(ttl=3600)
    def load_assets():
        geojson = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json") as f: geojson = json.load(f)
        else:
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
        # Handle cases where anchors might not have Tract IDs by providing a default or mapping logic
        if 'Tract' not in anchors.columns: anchors['Tract'] = "22071001700" # Dummy if missing
        
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['Eligibility_Status'] = master[elig_col].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible')
        return geojson, master, anchors

    gj, master_df, anchors_df = load_assets()

    # --- SECTIONS 1-4 (Fixed Content) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1-4</div><div class='section-title'>Executive Summary & Framework</div><p class='narrative-text'>Louisiana OZ 2.0 leverages federal tax incentives to drive capital into high-impact census tracts.</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAP WITH METRIC CARD ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Industrial & Community Assets</div></div>", unsafe_allow_html=True)
    
    a_col_left, a_col_right = st.columns([7, 3])
    
    with a_col_left:
        selected_types = st.multiselect("Filter Asset Type:", options=sorted(anchors_df['Type'].unique().tolist()), default=sorted(anchors_df['Type'].unique().tolist()), key="asset_filter")
        filtered_anchors = anchors_df[anchors_df['Type'].isin(selected_types)]

        fig_assets = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", 
            color_discrete_map={"Eligible": "rgba(74, 222, 128, 0.15)", "Ineligible": "rgba(30,41,59,0.05)"},
            mapbox_style="carto-darkmatter", zoom=6.2, center={"lat": 30.8, "lon": -91.8}
        )
        fig_assets.add_trace(go.Scattermapbox(
            lat=filtered_anchors["Lat"], lon=filtered_anchors["Lon"], mode='markers',
            marker=go.scattermapbox.Marker(size=7, color='#4ade80', opacity=0.8),
            text=filtered_anchors["Name"] + " (" + filtered_anchors["Type"] + ")",
            customdata=filtered_anchors["Tract"] if "Tract" in filtered_anchors.columns else [None]*len(filtered_anchors),
            hoverinfo='text'
        ))
        fig_assets.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=450, showlegend=False)
        asset_selection = st.plotly_chart(fig_assets, use_container_width=True, on_select="rerun", key="asset_map")

    with a_col_right:
        # Default tract if nothing selected
        active_tract = "22071001700" 
        if asset_selection and asset_selection.get("selection", {}).get("points"):
            # Try to get Tract from customdata or location
            point = asset_selection["selection"]["points"][0]
            active_tract = point.get("location") or point.get("customdata") or active_tract
        
        # Filter anchors specifically for this tract
        tract_assets = anchors_df[anchors_df['Tract'].astype(str) == str(active_tract)]
        
        st.markdown(f"#### Assets in Tract {active_tract}")
        st.markdown(f"<div class='metric-card'><div class='metric-value'>{len(tract_assets)}</div><div class='metric-label'>Total Proximate Assets</div></div>", unsafe_allow_html=True)
        
        if not tract_assets.empty:
            for cat in tract_assets['Type'].unique():
                count = len(tract_assets[tract_assets['Type'] == cat])
                st.markdown(f"<div class='asset-list-item'><b>{cat}:</b> {count} found</div>", unsafe_allow_html=True)
        else:
            st.info("Select a tract on the map to see local assets.")

    # --- SECTION 6: RECOMMENDATION TOOL ---
    st.markdown("<div class='content-section' style='border-bottom:none;'><div class='section-num'>SECTION 6</div><div class='section-title'>OZ 2.0 Recommendation Tool</div></div>", unsafe_allow_html=True)
    
    if "recommendation_log" not in st.session_state:
        st.session_state["recommendation_log"] = []

    m_col, p_col = st.columns([7, 3])
    with m_col:
        fig_rec = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.2)"},
            mapbox_style="carto-darkmatter", zoom=6.0, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
        )
        fig_rec.update_layout(coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=400)
        rec_selection = st.plotly_chart(fig_rec, use_container_width=True, on_select="rerun", key="rec_map")
    
    with p_col:
        current_id = "22071001700"
        if rec_selection and rec_selection.get("selection", {}).get("points"):
            current_id = str(rec_selection["selection"]["points"][0]["location"])
        
        st.markdown(f"**Tract {current_id}**")
        justification = st.text_area("Narrative Input", label_visibility="collapsed", placeholder="Justification...", height=100)
        
        if st.button("Log", use_container_width=True, type="primary"):
            if justification and current_id not in [x['Tract'] for x in st.session_state["recommendation_log"]]:
                st.session_state["recommendation_log"].append({"Tract": current_id, "Narrative": justification})
                st.rerun()

    if st.session_state["recommendation_log"]:
        st.dataframe(pd.DataFrame(st.session_state["recommendation_log"]), use_container_width=True, hide_index=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())