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

# --- 1. AUTHENTICATION & CONNECTION ---
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
                    st.session_state["user_display"] = u
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
        .content-section { padding: 30px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.7rem; font-weight: 900; color: #4ade80; margin-bottom: 2px; letter-spacing: 0.1em; }
        .section-title { font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; }
        .metric-card { background: #111827; padding: 12px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; margin-bottom: 10px; height: 105px; }
        .metric-value { font-size: 1.3rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.65rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 4px; }
        .rec-box { background: #161b28; border: 1px solid #4ade80; border-radius: 8px; padding: 20px; margin-top: 10px; }
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
                r = requests.get(geo_url, timeout=10)
                if r.status_code == 200: geojson = r.json()
            except: pass

        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['Eligibility_Status'] = master[elig_col].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        return geojson, master, anchors

    gj, master_df, anchors_df = load_assets()

    # --- SECTIONS 1-5 (NARRATIVE & ASSET MAP) ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1-5</div><div class='section-title'>Louisiana OZ 2.0: Strategy & Asset Alignment</div></div>", unsafe_allow_html=True)
    
    # Static Map Display
    if gj:
        fig_assets = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", color_discrete_map={"Eligible": "rgba(74, 222, 128, 0.2)", "Ineligible": "rgba(30,41,59,0.1)"},
            mapbox_style="carto-darkmatter", zoom=6.2, center={"lat": 30.8, "lon": -91.8}
        )
        fig_assets.add_trace(go.Scattermapbox(lat=anchors_df["Lat"], lon=anchors_df["Lon"], mode='markers', marker=go.scattermapbox.Marker(size=7, color='#4ade80', opacity=0.6)))
        fig_assets.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=400, showlegend=False)
        st.plotly_chart(fig_assets, use_container_width=True, key="asset_map_static")

    # --- SECTION 6: INTERACTIVE METRIC TOOL ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Engine</div></div>", unsafe_allow_html=True)
    
    m_col, p_col = st.columns([6, 4])
    
    with m_col:
        fig_rec = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.3)"},
            mapbox_style="carto-darkmatter", zoom=6.0, center={"lat": 30.8, "lon": -91.8}, opacity=0.8
        )
        fig_rec.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=600, showlegend=False)
        rec_selection = st.plotly_chart(fig_rec, use_container_width=True, on_select="rerun", key="rec_map_interactive")
    
    with p_col:
        sel_id = "22071001700" # Default
        if rec_selection and rec_selection.get("selection", {}).get("points"):
            sel_id = str(rec_selection["selection"]["points"][0]["location"])
        
        row = master_df[master_df["geoid_str"] == sel_id]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"### Tract {sel_id} <br><small style='color:#4ade80;'>{str(d.get('Parish', '')).upper()}</small>", unsafe_allow_html=True)
            
            def m_card(label, val, suffix=""):
                v = pd.to_numeric(val, errors='coerce')
                disp = "N/A" if np.isnan(v) else f"{v:,.1f}{suffix}"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{disp}</div><div class='metric-label'>{label}</div></div>", unsafe_allow_html=True)

            c1, c2, c3 = st.columns(3)
            with c1:
                m_card("Poverty", d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0), "%")
                m_card("Unemployment", d.get('Unemployment Rate', 0), "%")
                m_card("Minority Pop", d.get('Percent Minority Population', 0), "%")
            with c2:
                m_card("Med. Income", d.get('Estimate!!Median household income in the past 12 months (in 2023 inflation-adjusted dollars)', 0), "$")
                m_card("Internet", d.get('Percent Households with Broadband', 0), "%")
                m_card("Vacancy", d.get('Percent Vacant Units', 0), "%")
            with c3:
                m_card("Labor Force", d.get('Labor Force Participation Rate', 0), "%")
                m_card("Education", d.get('Percent Bachelor\'s Degree or Higher', 0), "%")
                m_card("Rent Burden", d.get('Median Gross Rent as % of Household Income', 0), "%")

            with st.container():
                st.markdown("<div class='rec-box'>", unsafe_allow_html=True)
                justification = st.text_area("Investment Rationale", placeholder="Enter justification for this recommendation...", key="just_text")
                if st.button("Submit Recommendation", use_container_width=True, type="primary"):
                    if "recommendation_log" not in st.session_state: st.session_state["recommendation_log"] = []
                    new_entry = {
                        "User": st.session_state["user_display"],
                        "Tract": sel_id, 
                        "Parish": d.get('Parish'), 
                        "Justification": justification,
                        "Timestamp": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
                    }
                    st.session_state["recommendation_log"].append(new_entry)
                    st.success("Recommendation added to temporary log.")
                st.markdown("</div>", unsafe_allow_html=True)

    # --- RECOMMENDATION HUB (BELOW SECTION 6) ---
    st.write("---")
    st.markdown("### 🏛️ My Recommendation Hub")
    
    if "recommendation_log" in st.session_state and st.session_state["recommendation_log"]:
        log_df = pd.DataFrame(st.session_state["recommendation_log"])
        
        # Dashboard Overview
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total Tracts Recommended", len(log_df))
        kpi2.metric("Parishes Represented", log_df['Parish'].nunique())
        kpi3.download_button("Export as CSV", log_df.to_csv(index=False), "my_recommendations.csv", "text/csv")

        # Visual Table
        st.dataframe(log_df, use_container_width=True, hide_index=True)
        
        if st.button("Clear My Log"):
            st.session_state["recommendation_log"] = []
            st.rerun()
    else:
        st.info("No recommendations logged yet. Select a green tract on the map above to begin your advocacy.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())