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

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- HELPERS ---
def safe_float(val):
    try:
        if pd.isna(val) or val == '' or val == 'N/A': return 0.0
        s = str(val).replace('$', '').replace(',', '').replace('%', '').replace('"', '').strip()
        return float(s)
    except: return 0.0

def safe_int(val):
    return int(safe_float(val))

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
            st.error("Invalid username or password")
        except Exception as e:
            st.error(f"Error connecting to database: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
            .stApp { background-color: #0b0f19 !important; font-family: 'Inter', sans-serif; }
            div[data-testid="stVerticalBlock"] > div:has(input) {
                background-color: #111827; padding: 40px; border-radius: 15px;
                border: 1px solid #1e293b; box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }
            label { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.05em; }
            input { background-color: #0b0f19 !important; color: white !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; }
            button[kind="primary"], .stButton > button { background-color: #4ade80 !important; color: #0b0f19 !important; font-weight: 900 !important; border: none !important; height: 3em !important; margin-top: 10px; }
            button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(74, 222, 128, 0.3); }
            .login-header { text-align: center; margin-bottom: 2rem; }
            </style>
        """, unsafe_allow_html=True)

        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("""
                <div class="login-header">
                    <p style='color: #4ade80; font-weight: 900; letter-spacing: 0.2em; font-size: 0.8rem; margin-bottom: 0;'>SECURE ACCESS</p>
                    <h1 style='color: white; font-weight: 900; margin-top: 0;'>OZ 2.0 Portal</h1>
                </div>
            """, unsafe_allow_html=True)
            with st.container():
                st.text_input("Username", key="username", placeholder="Enter your username")
                st.text_input("Password", type="password", key="password", placeholder="••••••••")
                st.button("Sign In", on_click=password_entered, use_container_width=True)
            st.markdown("<p style='text-align:center; color:#475569; font-size:0.8rem; margin-top:20px;'>Louisiana Opportunity Zones 2.0 | Admin Access Only</p>", unsafe_allow_html=True)
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING & FROZEN NAV ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link, .nav-link:link, .nav-link:visited { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; transition: color 0.3s ease; }
        .nav-link:hover, .nav-link:active { color: #4ade80 !important; text-decoration: none !important; }
        .main .block-container { padding-top: 80px !important; }
        div[data-baseweb="select"] > div { background-color: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 6px !important; }
        div[data-baseweb="select"] * { color: #0f172a !important; }
        label[data-testid="stWidgetLabel"] { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.05em; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 0.95rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        .anchor-card { background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }
        .view-site-btn { display: block; background-color: #4ade80; color: #0b0f19 !important; padding: 8px 0; border-radius: 4px; text-decoration: none !important; font-size: 0.75rem; font-weight: 900; text-align: center; margin-top: 10px; border: 1px solid #4ade80; transition: all 0.2s; cursor: pointer; }
        .view-site-btn:hover { background-color: #22c55e; border-color: #22c55e; }
        </style>
        <div class="nav-container">
            <a class="nav-link" href="#section-1">Overview</a>
            <a class="nav-link" href="#section-5">Mapping</a>
            <a class="nav-link" href="#section-6">Report</a>
        </div>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 3956 * 2 * asin(sqrt(a))

    @st.cache_data(ttl=3600)
    def load_assets():
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        def read_csv_with_fallback(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)

        # Sourcing from the requested V2 file
        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File (V2).csv")
        master['geoid_str'] = master['GEOID'].astype(str).str.zfill(11)
        
        # Mapping Column D (OZ 1.0) and Column E (OZ 2.0)
        master['OZ1_Status'] = master['Current OZ 1.0 tract (expires Dec. 2028)'].apply(lambda x: 'Yes' if str(x).strip().lower() == 'yes' else 'No')
        master['OZ2_Status'] = master['Eligibility for OZ 2.0 Designation'].apply(lambda x: 'Eligible' if str(x).strip().upper() == 'ELIGIBLE' else 'Ineligible')

        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    if geom['type'] == 'Polygon': pts = np.array(geom['coordinates'][0])
                    elif geom['type'] == 'MultiPolygon': pts = np.array(geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SIDEBAR TOGGLES ---
    st.sidebar.header("Map Layers")
    show_oz1 = st.sidebar.checkbox("Highlight Current OZ 1.0 (2028)", value=False)

    def get_zoom_center(geoids):
        if not geoids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.0
        lats, lons = [], []
        id_key = "GEOID" if "GEOID" in str(gj['features'][0]['properties']) else "GEOID20"
        for feature in gj['features']:
            gid = feature['properties'].get(id_key)
            if gid in geoids:
                geom = feature['geometry']
                if geom['type'] == 'Polygon':
                    coords = np.array(geom['coordinates'][0])
                    lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
                elif geom['type'] == 'MultiPolygon':
                    for poly in geom['coordinates']:
                        coords = np.array(poly[0])
                        lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
        if not lats: return {"lat": 30.9, "lon": -91.8}, 6.0
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)
        center = {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}
        max_diff = max(max_lat - min_lat, max_lon - min_lon)
        zoom = 11.0 if max_diff < 0.1 else 8.5 if max_diff < 0.8 else 6.2
        return center, zoom

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        
        # Color Logic: 0=Default, 1=OZ 2.0 (Green), 2=Selected (Orange), 3=OZ 1.0 (Blue)
        def get_color_cat(row):
            if row['geoid_str'] in selected_geoids: return 2
            if show_oz1 and row['OZ1_Status'] == 'Yes': return 3
            return 1 if row['OZ2_Status'] == 'Eligible' else 0
        
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        focus_geoids = {st.session_state["active_tract"]} if st.session_state.get("active_tract") else set(map_df['geoid_str'].tolist())
        center, zoom = get_zoom_center(focus_geoids)
        
        fig = go.Figure()
        fig.add_trace(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.33, '#4ade80'], [0.66, '#f97316'], [1, '#3b82f6']], 
            zmin=0, zmax=3, showscale=False, 
            marker=dict(opacity=0.6, line=dict(width=0.5, color='white')),
            hoverinfo="location", name="Census Tracts"
        ))

        # Anchor Pins Logic
        anchor_types = sorted(anchors_df['Type'].unique())
        color_palette = px.colors.qualitative.Bold 
        for i, a_type in enumerate(anchor_types):
            type_data = anchors_df[anchors_df['Type'] == a_type]
            fig.add_trace(go.Scattermapbox(
                lat=type_data['Lat'], lon=type_data['Lon'], mode='markers',
                marker=go.scattermapbox.Marker(size=12, color=color_palette[i % len(color_palette)]),
                text=type_data['Name'], name=a_type, visible="legendonly"
            ))

        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, height=700, clickmode='event+select'
        )
        return fig

    # --- SECTIONS ---
    st.markdown("<div id='section-5'></div>", unsafe_allow_html=True)
    st.header("Strategic Mapping Portal (OZ 2.0)")
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    with f_col2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    with f_col3:
        tract_list = ["Search Tract GEOID..."] + sorted([str(x) for x in filtered_df['geoid_str'].tolist()])
        selected_search = st.selectbox("Find Census Tract", tract_list)
        if selected_search != "Search Tract GEOID...":
            st.session_state["active_tract"] = selected_search

    combined_map = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="oz_map")
    
    if combined_map and "selection" in combined_map and combined_map["selection"]["points"]:
        st.session_state["active_tract"] = str(combined_map["selection"]["points"][0]["location"])
        st.rerun()

    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == str(curr)].iloc[0]
        
        st.markdown(f"### Parish: {row['Parish']} (Tract {curr})")
        
        m_col1, m_col2 = st.columns([0.6, 0.4])
        with m_col1:
            st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem; letter-spacing:0.15em;'>TRACT METRICS</p>", unsafe_allow_html=True)
            met_cols = st.columns(3)
            # UPDATED: Metro Status now from Column G
            met_cols[0].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Rural Eligibility for OZ 2.0', 'N/A')}</div><div class='metric-label'>Metro Status (Col G)</div></div>", unsafe_allow_html=True)
            met_cols[1].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('OZ2_Status')}</div><div class='metric-label'>2.0 Eligibility</div></div>", unsafe_allow_html=True)
            met_cols[2].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('NMTC Basic Eligibility')}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            
            met_cols2 = st.columns(3)
            met_cols2[0].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Poverty %')}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            met_cols2[1].markdown(f"<div class='metric-card'><div class='metric-value'>${row.get('Median Household Income')}</div><div class='metric-label'>MHI</div></div>", unsafe_allow_html=True)
            met_cols2[2].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Unemploy  %')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)

        with m_col2:
            st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem; letter-spacing:0.15em;'>NEARBY ANCHORS</p>", unsafe_allow_html=True)
            if curr in tract_centers:
                lon, lat = tract_centers[curr]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                for _, a in anchors_df.sort_values('dist').head(3).iterrows():
                    st.markdown(f"**{a['Name']}** ({a['dist']:.1f} mi)")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())