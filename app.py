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

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana OZ 2.0 Command Center", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
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

def read_csv_with_fallback(path):
    for enc in ['utf-8', 'latin1', 'cp1252']:
        try: return pd.read_csv(path, encoding=enc)
        except: continue
    return pd.read_csv(path)

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
        except: pass

    if not st.session_state["password_correct"]:
        st.markdown("<style>.stApp { background-color: #0b0f19; }</style>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<h2 style='text-align:center; color:white;'>OZ 2.0 Portal</h2>", unsafe_allow_html=True)
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
        
        /* Dashboard Cards */
        .dashboard-card {
            background-color: #111827; padding: 20px; border: 1px solid #1e293b;
            border-radius: 12px; height: 500px; overflow-y: auto;
        }
        .card-title { color: #4ade80; font-weight: 900; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 15px; letter-spacing: 0.1em; }
        
        /* Metrics */
        .metric-mini { background: #1f2937; padding: 10px; border-radius: 8px; border: 1px solid #374151; text-align: center; margin-bottom: 10px; }
        .m-val { color: #4ade80; font-size: 1.1rem; font-weight: 900; }
        .m-lab { color: #94a3b8; font-size: 0.6rem; text-transform: uppercase; }

        /* Anchor List */
        .anchor-item { border-bottom: 1px solid #1e293b; padding: 10px 0; }
        .anchor-name { font-weight: 700; font-size: 0.9rem; color: #f8fafc; }
        .anchor-dist { font-size: 0.75rem; color: #4ade80; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA & ASSETS ---
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
        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        anchors = read_csv_with_fallback("la_anchors.csv")
        
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    coords = feature['geometry']['coordinates']
                    if feature['geometry']['type'] == 'MultiPolygon': pts = np.array(coords[0][0])
                    else: pts = np.array(coords[0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- 4. SIDEBAR TABLE OF CONTENTS ---
    with st.sidebar:
        st.title("Navigation")
        nav = st.radio("Go to Section:", ["Command Center", "Benefit Framework", "Strategic Advocacy", "Recommendation Report"])
        st.divider()
        if st.button("Reset Session"):
            st.session_state["active_tract"] = None
            st.rerun()

    # --- 5. MAP LOGIC (SHARED) ---
    def get_zoom_center(geoids):
        active = st.session_state.get("active_tract")
        target_ids = [active] if active else geoids
        if not target_ids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.5
        
        lats, lons = [], []
        for feature in gj['features']:
            gid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
            if gid in target_ids:
                geom = feature['geometry']
                coords = geom['coordinates'] if geom['type'] == 'Polygon' else geom['coordinates'][0]
                for poly in coords:
                    pts = np.array(poly)
                    if pts.ndim == 2:
                        lons.extend(pts[:, 0]); lats.extend(pts[:, 1])
        
        if not lats: return {"lat": 30.9, "lon": -91.8}, 6.5
        center = {"lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2}
        zoom = 12 if active else 7
        return center, zoom

    def render_unified_map(df):
        map_df = df.copy()
        recs = [r['Tract'] for r in st.session_state["session_recs"]]
        map_df['Color_Cat'] = map_df.apply(lambda r: 2 if r['geoid_str'] in recs else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        
        center, zoom = get_zoom_center(map_df['geoid_str'].tolist())
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Cat'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#334155'], [0.5, '#4ade80'], [1, '#f97316']],
            zmin=0, zmax=2, showscale=False, marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, height=500, clickmode='event+select',
            uirevision=st.session_state.get("active_tract", "const")
        )
        return fig

    # --- 6. PAGE RENDERING BASED ON NAV ---
    if nav == "Command Center":
        st.markdown("<h2 style='margin-bottom:0;'>Strategic Command Center</h2>", unsafe_allow_html=True)
        st.markdown("<p style='color:#94a3b8;'>Consolidated Tract Analysis & Profiling</p>", unsafe_allow_html=True)
        
        # Filter Row
        f1, f2, f3 = st.columns([1, 1, 1])
        with f1: region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
        filtered = master_df.copy()
        if region != "All Louisiana": filtered = filtered[filtered['Region'] == region]
        
        with f2: parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered['Parish'].dropna().unique().tolist()))
        if parish != "All in Region": filtered = filtered[filtered['Parish'] == parish]
        
        with f3: 
            search = st.text_input("Search Census Tract (11-digit FIPS)", placeholder="e.g. 22071001745")
            if search and search in master_df['geoid_str'].values:
                st.session_state["active_tract"] = search

        # Map
        map_res = st.plotly_chart(render_unified_map(filtered), use_container_width=True, on_select="rerun")
        if map_res and "selection" in map_res and map_res["selection"]["points"]:
            st.session_state["active_tract"] = str(map_res["selection"]["points"][0]["location"])
            st.rerun()

        # The 3-Cell Grid
        st.markdown("---")
        c1, c2, c3 = st.columns(3)
        curr_id = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr_id].iloc[0] if curr_id else None

        with c1:
            st.markdown("<div class='dashboard-card'><div class='card-title'>📍 Anchor Assets</div>", unsafe_allow_html=True)
            a_type = st.selectbox("Filter Anchors", ["All"] + sorted(anchors_df['Type'].unique().tolist()))
            if curr_id and curr_id in tract_centers:
                lon, lat = tract_centers[curr_id]
                wa = anchors_df.copy()
                if a_type != "All": wa = wa[wa['Type'] == a_type]
                wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                for _, a in wa.sort_values('dist').head(8).iterrows():
                    st.markdown(f"<div class='anchor-item'><div class='anchor-name'>{a['Name']}</div><div class='anchor-dist'>{a['dist']:.1f} miles away</div></div>", unsafe_allow_html=True)
            else: st.info("Select a tract to see anchors.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c2:
            st.markdown("<div class='dashboard-card'><div class='card-title'>📊 Tract Data Profile</div>", unsafe_allow_html=True)
            if row is not None:
                st.markdown(f"**Tract {curr_id}**")
                m_a, m_b = st.columns(2)
                m_a.markdown(f"<div class='metric-mini'><div class='m-val'>{safe_float(row.get('Unemployment Rate (%)')):.1f}%</div><div class='m-lab'>Unemployment</div></div>", unsafe_allow_html=True)
                m_b.markdown(f"<div class='metric-mini'><div class='m-val'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)')):,.0f}</div><div class='m-lab'>Median Income</div></div>", unsafe_allow_html=True)
                st.markdown(f"**Metro Status:** {row.get('Metro Status (Metropolitan/Rural)')}")
                st.progress(safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined'))/100, text="Poverty Level")
            else: st.info("Select a tract to view data.")
            st.markdown("</div>", unsafe_allow_html=True)

        with c3:
            st.markdown("<div class='dashboard-card'><div class='card-title'>✍️ Narrative Justification</div>", unsafe_allow_html=True)
            inv_cat = st.selectbox("Investment Category", ["Industrial", "Multi-Family", "Mixed-Use", "Infrastructure"])
            just_text = st.text_area("Justification Notes", height=200, placeholder="INSTRUCTIONS: To justify OZ 2.0 eligibility, highlight:\n1. Proximity to anchors listed in Cell 1.\n2. Gap in local capital stack.\n3. Alignment with regional economic goals.\n4. Specific project readiness (e.g. site control).")
            if st.button("Add to Selection Report", use_container_width=True, type="primary"):
                if curr_id:
                    st.session_state["session_recs"].append({"Tract": curr_id, "Category": inv_cat, "Justification": just_text})
                    st.toast("Tract saved!")
                else: st.error("Please select a tract on the map first.")
            st.markdown("</div>", unsafe_allow_html=True)

    elif nav == "Benefit Framework":
        st.header("Benefit Framework")
        st.write("Detailed breakdown of tax deferral, basis step-up, and permanent exclusion rules.")

    elif nav == "Strategic Advocacy":
        st.header("Strategic Advocacy")
        st.write("Criteria for high-readiness tracts and federal distress definitions.")

    elif nav == "Recommendation Report":
        st.header("Recommendation Report")
        if st.session_state["session_recs"]:
            st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True)
        else:
            st.info("No recommendations added yet.")