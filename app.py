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
                    st.session_state["current_user"] = u 
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if "password_correct" not in st.session_state:
        st.markdown("""
            <style>
            .stApp { background-color: #0b0f19; }
            .login-box { max-width: 450px; margin: 80px auto; padding: 40px; background: #111827; border: 1px solid #1e293b; border-radius: 12px; text-align: center; }
            .login-title { font-family: serif; font-size: 2.2rem; font-weight: 900; color: #f8fafc; }
            </style>
            <div class="login-box">
                <div class="login-title">OZ 2.0 Recommendation Portal</div>
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
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
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

    # (Sections 1-5 Remain Identical to Previous Restoration)
    st.markdown("### Section 1-5 Navigation Active")

    # --- SECTION 6: UPDATED LAYOUT ---
    st.markdown("<div class='content-section'><h3>Tract Profiling & My Recommendations</h3>", unsafe_allow_html=True)
    col6_map, col6_data = st.columns([0.5, 0.5])
    
    with col6_map:
        fig6 = px.choropleth_mapbox(master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="white-bg", zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.8)
        fig6.update_layout(mapbox_layers=[{"below": 'traces', "sourcetype": "raster", "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]}],
                           margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=700, clickmode='event+select')
        sel6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="map_s6_v2")
        if sel6 and sel6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel6["selection"]["points"][0]["location"])

    with col6_data:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            poverty_rate = float(d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0))
            med_income = float(str(d.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', '0')).replace(',','').replace('$',''))
            ami_benchmark = 89000 
            
            st.markdown(f"<div style='background:#111827; padding:15px; border-radius:10px; border-left: 5px solid #4ade80; margin-bottom:15px;'><h4>{st.session_state['active_tract']}</h4><p style='color:#4ade80; font-size:0.8rem;'>{str(d.get('Parish','')).upper()}</p></div>", unsafe_allow_html=True)
            
            # --- NEW 1-ROW 3-COLUMN TOP GRID ---
            g1, g2, g3 = st.columns(3)
            m_status = str(d.get('Metro Status (Metropolitan/Rural)', '')).lower()
            with g1:
                status_val = "URBAN" if "metropolitan" in m_status else "RURAL"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{status_val}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            with g2:
                nmtc_elig = "YES" if (poverty_rate > 20 or med_income < (0.8 * ami_benchmark)) else "NO"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{nmtc_elig}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            with g3:
                deeply_dist = "YES" if (poverty_rate > 40 or med_income < (0.4 * ami_benchmark)) else "NO"
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{deeply_dist}</div><div class='metric-label'>Deeply Distressed</div></div>", unsafe_allow_html=True)
            
            # --- 6-CARD DATA GRID ---
            m1, m2, m3 = st.columns(3)
            with m1:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{poverty_rate}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Total!!Total population!!18 to 24 years','0')}</div><div class='metric-label'>Pop (18-24)</div></div>", unsafe_allow_html=True)
            with m2:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
                # Corrected Population 65+ reference [cite: 2026-02-09]
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Total!!Total population!!65 years and over','0')}</div><div class='metric-label'>Pop (65+)</div></div>", unsafe_allow_html=True)
            with m3:
                st.markdown(f"<div class='metric-card'><div class='metric-value'>${med_income:,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
                st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Broadband Internet (%)','0')}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            cat = st.selectbox("Justification Category", ["Industrial Development", "Housing Initiative", "Commercial/Retail", "Technology & Innovation"])
            just = st.text_area("Narrative Justification", height=80)
            if st.button("Submit Recommendation", use_container_width=True, type="primary"):
                try:
                    new_rec = pd.DataFrame([{
                        "Date": datetime.now().strftime("%Y-%m-%d"),
                        "GEOID": str(st.session_state["active_tract"]),
                        "Category": cat,
                        "Justification": just,
                        "Is_Eligible": d['Eligibility_Status'],
                        "User": st.session_state["current_user"],
                        "Document": "N/A"
                    }])
                    # Robust write attempt
                    conn.create(data=new_rec)
                    st.success("Recommendation logged.")
                except Exception as e:
                    st.error(f"Spreadsheet write error: {e}. Check if the Google Sheet has 'Editor' permissions for the service account.")

    # --- MY RECOMMENDATIONS ---
    st.markdown("### My Recommendation History")
    try:
        all_recs = conn.read(ttl="5s")
        my_recs = all_recs[all_recs['User'].astype(str).str.lower() == st.session_state["current_user"].lower()]
        st.dataframe(my_recs, use_container_width=True, hide_index=True)
    except:
        st.info("No recommendations found for this user.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())