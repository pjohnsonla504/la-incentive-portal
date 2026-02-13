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

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None # Start with no selection
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- HELPER FUNCTIONS ---
def clean_currency(val):
    if pd.isna(val) or val == 'N/A' or val == '': 
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    try:
        return float(str(val).replace('$', '').replace(',', '').strip())
    except:
        return 0.0

# --- 1. AUTHENTICATION (Standard logic) ---
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
                    st.session_state["current_user"] = u 
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            .stApp { background-color: #0b0f19; }
            .login-card { max-width: 360px; margin: 140px auto 20px auto; padding: 30px; background: #111827; border: 1px solid #1e293b; border-top: 4px solid #4ade80; border-radius: 12px; text-align: center; }
            .login-title { font-family: 'Inter', sans-serif; font-size: 1.5rem; font-weight: 900; color: #ffffff; margin-bottom: 4px; }
            label, p, .stText { color: #ffffff !important; font-weight: 600 !important; }
            input { color: #000000 !important; }
            </style>
            <div class="login-card">
                <div class="login-title">OZ 2.0 Portal</div>
                <div style="color:#4ade80; font-size:0.7rem; text-transform:uppercase; letter-spacing:0.1em;">Secure Stakeholder Access</div>
            </div>
        """, unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Sign In", on_click=password_entered, use_container_width=True, type="primary")
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
        .tract-header-container { background-color: #111827 !important; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; margin-bottom: 15px; border: 1px solid #1e293b; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 12px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 5px; }
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
        
        # Track Eligibility for highlighting
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        
        anchors = read_csv_safe("la_anchors.csv")
        centers = {}
        if geojson:
            for feature in geojson['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    coords = np.array(feature['geometry']['coordinates'][0]) if feature['geometry']['type'] == 'Polygon' else np.array(feature['geometry']['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- UPDATED RENDERER FOR MIRRORED SELECTION ---
    def render_map(df, is_filtered=False, height=600):
        recs = [str(r["Tract ID"]) for r in st.session_state["session_recs"]]
        map_df = df.copy().reset_index(drop=True)
        
        map_df.loc[map_df['geoid_str'].isin(recs), 'Eligibility_Status'] = "Recommended"

        # Determine which index is currently active to force the Plotly selection highlight
        selected_indices = []
        if st.session_state["active_tract"]:
            matches = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist()
            if matches:
                selected_indices = matches

        center = {"lat": 30.8, "lon": -91.8}
        zoom = 6.2 
        if is_filtered and not map_df.empty:
            active_ids = map_df['geoid_str'].tolist()
            subset_centers = [tract_centers[gid] for gid in active_ids if gid in tract_centers]
            if subset_centers:
                lons, lats = zip(*subset_centers)
                center = {"lat": np.mean(lats), "lon": np.mean(lons)}
                zoom = 8.5 
        
        fig = px.choropleth_mapbox(map_df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", 
                                     color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#cbd5e1", "Recommended": "#f97316"},
                                     mapbox_style="carto-positron", zoom=zoom, center=center, opacity=0.5)
        
        # This core line enables the mirroring of the "Interactive Cross-filtering" look
        fig.update_traces(selectedpoints=selected_indices, selector=dict(type='choropleth_mapbox'))

        fig.update_layout(
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', 
            showlegend=True, height=height, clickmode='event+select', uirevision="constant" 
        )
        return fig

    chart_config = {"scrollZoom": True}

    # --- SECTION 5: ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    
    unique_regions = sorted(master_df['Region'].dropna().unique().tolist())
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_region = st.selectbox("Filter by Region", ["All Louisiana"] + unique_regions)
    with f_col2:
        available_parishes = sorted(master_df[master_df['Region'] == selected_region]['Parish'].dropna().unique().tolist()) if selected_region != "All Louisiana" else sorted(master_df['Parish'].dropna().unique().tolist())
        selected_parish = st.selectbox("Filter by Parish", ["All in Region"] + available_parishes)
    with f_col3: selected_asset_type = st.selectbox("Filter by Anchor Asset Type", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist() if 'Type' in anchors_df.columns else []))

    filtered_df = master_df.copy()
    is_actively_filtering = (selected_region != "All Louisiana" or selected_parish != "All in Region")
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]

    c5a, c5b = st.columns([0.6, 0.4], gap="large") 
    with c5a:
        f5 = render_map(filtered_df, is_filtered=is_actively_filtering, height=600)
        s5 = st.plotly_chart(f5, use_container_width=True, on_select="rerun", key="map5", config=chart_config)
        if s5 and "selection" in s5 and s5["selection"]["points"]:
            new_id = str(s5["selection"]["points"][0]["location"])
            st.session_state["active_tract"] = new_id
            st.rerun()

    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>ANCHOR ASSETS NEAR {curr if curr else 'SELECTION'}</p>", unsafe_allow_html=True)
        list_html = ""
        if curr and curr in tract_centers:
            lon, lat = tract_centers[curr]
            working_anchors = anchors_df.copy()
            working_anchors['dist'] = working_anchors.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in working_anchors.sort_values('dist').head(12).iterrows():
                list_html += f"<div style='background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px;'><div style='color:#4ade80; font-size:0.65rem; font-weight:900;'>{str(a.get('Type','')).upper()}</div><div style='color:#ffffff; font-weight:700; font-size:1rem; margin: 4px 0;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.75rem;'>📍 {a['dist']:.1f} miles away</div></div>"
        components.html(f"<div style='height: 530px; overflow-y: auto; font-family: sans-serif;'>{list_html}</div>", height=550)

    # --- SECTION 6: MIRRORED PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.6, 0.4], gap="large") 
    with c6a:
        f6 = render_map(filtered_df, is_filtered=is_actively_filtering, height=600)
        s6 = st.plotly_chart(f6, use_container_width=True, on_select="rerun", key="map6", config=chart_config)
        if s6 and "selection" in s6 and s6["selection"]["points"]:
            new_id = str(s6["selection"]["points"][0]["location"])
            st.session_state["active_tract"] = new_id
            st.rerun()

    with c6b:
        if st.session_state["active_tract"]:
            row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
            if not row.empty:
                d = row.iloc[0]
                st.markdown(f"<div class='tract-header-container'><div style='font-size: 2rem; font-weight: 900; color: #4ade80;'>{str(d.get('Parish','')).upper()}</div><div style='color: #94a3b8;'>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
                # (Metrics and recommendation buttons would follow here as in previous script)
        else:
            st.info("Select a tract on the map to view data profiling.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())