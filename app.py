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
        s = str(val).replace('$', '').replace(',', '').replace('%', '').strip()
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
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .nav-link:hover { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; }
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
        
        def read_clean_csv(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: 
                    df = pd.read_csv(path, encoding=enc)
                    df.columns = df.columns.str.strip() # REMOVE WHITESPACE FROM HEADERS
                    return df
                except: continue
            return pd.read_csv(path)

        master = read_clean_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )

        anchors = read_clean_csv("la_anchors.csv")
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

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        map_df['Color_Category'] = map_df.apply(lambda r: 2 if r['geoid_str'] in selected_geoids else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], 
            zmin=0, zmax=2, showscale=False, marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        
        # Add Anchor Pins
        color_palette = px.colors.qualitative.Bold
        for i, a_type in enumerate(sorted(anchors_df['Type'].unique())):
            type_data = anchors_df[anchors_df['Type'] == a_type]
            fig.add_trace(go.Scattermapbox(
                lat=type_data['Lat'], lon=type_data['Lon'], mode='markers',
                marker=go.scattermapbox.Marker(size=12, color=color_palette[i % len(color_palette)]),
                text=type_data['Name'], name=a_type, visible="legendonly"
            ))

        fig.update_layout(mapbox=dict(style="carto-positron", zoom=6, center={"lat": 30.9, "lon": -91.8}), margin={"r":0,"t":0,"l":0,"b":0}, height=600)
        return fig

    # --- MAIN UI ---
    st.markdown("<div id='section-5'></div><h2 style='font-weight:900;'>Strategic Mapping</h2>", unsafe_allow_html=True)
    
    col_a, col_b = st.columns([0.65, 0.35])
    
    with col_a:
        map_event = st.plotly_chart(render_map_go(master_df), use_container_width=True, on_select="rerun", key="main_map")
        if map_event and "selection" in map_event and map_event["selection"]["points"]:
            st.session_state["active_tract"] = str(map_event["selection"]["points"][0]["location"])

    with col_b:
        if st.session_state["active_tract"]:
            curr = st.session_state["active_tract"]
            row = master_df[master_df["geoid_str"] == curr].iloc[0]
            st.subheader(f"{row['Parish']} - {curr}")
            
            # Anchor Display with strict Link checking
            st.markdown("### Nearby Assets")
            if curr in tract_centers:
                lon, lat = tract_centers[curr]
                anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                nearby = anchors_df.sort_values('dist').head(10)
                
                list_html = ""
                for _, a in nearby.iterrows():
                    # ROBUST LINK CHECK: Header is stripped, we check for string content
                    link_html = ""
                    if 'Link' in a and pd.notna(a['Link']):
                        url = str(a['Link']).strip()
                        if url.startswith("http"):
                            link_html = f"<a href='{url}' target='_blank' style='display:block; background:#4ade80; color:#0b0f19; text-align:center; padding:5px; border-radius:4px; font-weight:900; text-decoration:none; margin-top:8px; font-size:0.7rem;'>VIEW SITE ↗</a>"
                    
                    type_style = "color:#f97316;" if a['Type'] == "Project Announcements" else "color:#4ade80;"
                    list_html += f"""
                    <div style='background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px;'>
                        <div style='{type_style} font-size:0.65rem; font-weight:900; text-transform:uppercase;'>{a['Type']}</div>
                        <div style='font-weight:800; color:white;'>{a['Name']}</div>
                        <div style='color:#94a3b8; font-size:0.75rem;'>{a['dist']:.1f} miles away</div>
                        {link_html}
                    </div>
                    """
                components.html(f"<body style='margin:0; font-family:sans-serif;'>{list_html}</body>", height=400, scrolling=True)
        else:
            st.info("Select a tract on the map to see nearby anchors and project announcements.")

    # --- REPORT ---
    st.markdown("<div id='section-6'></div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.write("### Export Recommendations")
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True)