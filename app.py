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
    st.session_state["active_tract"] = None 
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
            st.markdown("<h2 style='text-align:center; color:white; font-family: sans-serif;'>OZ 2.0 Portal</h2>", unsafe_allow_html=True)
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
        .hero-title { font-size: 3.2rem; font-weight: 900; color: #f8fafc; margin-bottom: 15px; }
        .hero-subtitle { color: #4ade80; font-size: 1.1rem; font-weight: 700; text-transform: uppercase; }
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 950px; margin-bottom: 25px; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #2d3748; border-radius: 8px; min-height: 200px; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; }
        .tract-header-container { background-color: #111827 !important; padding: 20px; border-radius: 10px; border-top: 4px solid #4ade80; border: 1px solid #1e293b; }
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
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        # FIX: Encoding handling for CSVs
        def read_csv_with_fallback(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except UnicodeDecodeError: continue
            return pd.read_csv(path)

        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        
        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    coords = np.array(feature['geometry']['coordinates'][0]) if feature['geometry']['type'] == 'Polygon' else np.array(feature['geometry']['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        sel_idx = []
        if st.session_state["active_tract"]:
            sel_idx = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist()

        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj,
            locations=map_df['geoid_str'],
            z=np.where(map_df['Eligibility_Status'] == 'Eligible', 1, 0),
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#cbd5e1'], [1, '#4ade80']],
            showscale=False,
            marker=dict(opacity=0.8, line=dict(width=0.5, color='white')),
            selectedpoints=sel_idx,
            selected=dict(marker=dict(opacity=1.0)),
            unselected=dict(marker=dict(opacity=0.1)),
            hoverinfo="location"
        ))

        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=6.2, center={"lat": 30.8, "lon": -91.8}),
            margin={"r":0,"t":0,"l":0,"b":0},
            paper_bgcolor='rgba(0,0,0,0)',
            height=600,
            clickmode='event+select',
            uirevision="constant"
        )
        return fig

    # --- SECTION 1: HERO ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>SECTION 1</div>
            <div class='hero-subtitle'>Opportunity Zones 2.0</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0 Recommendation Portal</div>
            <div class='narrative-text'>Opportunity Zones 2.0 is Louisiana’s chance to turn bold ideas into real investment—unlocking long-term private capital to fuel jobs, small businesses, and innovation in the communities that need it most.</div>
        </div>
    """, unsafe_allow_html=True)

    # --- SECTIONS 2-4: NARRATIVE ---
    narratives = {
        2: ("The OZ 2.0 Benefit Framework", "Our strategic framework leverages federal tax incentives to de-risk projects and encourage long-term equity investment in Louisiana's future.", [
            ("Capital Gain Deferral", "Defer taxes on original capital gains for 5 years."),
            ("Basis Step-Up", "Qualified taxpayer receives 10% basis step-up (30% if rural)."),
            ("Permanent Exclusion", "Zero federal capital gains tax on appreciation after 10 years.")
        ]),
        3: ("Census Tract Advocacy", "We focus on identifying tracts with high Project Readiness—pairing distressed community data with existing industrial and educational infrastructure.", [
            ("Geographically Disbursed", "Zones Focused on rural and investment ready tracts."),
            ("Distressed Communities", "Eligibility is dependent on the federal definition of a low-income community."),
            ("Project Ready", "Aligning regional recommendations with tracts likely to receive private investment.")
        ]),
        4: ("Best Practices", "Leveraging national expertise to ensure Louisiana's Opportunity Zones 2.0 implementation is best-in-class.", [
            ("Economic Innovation Group", "Proximity to ports and manufacturing hubs ensures long-term tenant demand."),
            ("Frost Brown Todd", "Utilizing local educational anchors to provide a skilled labor force."),
            ("America First Policy Institute", "Stack incentives to de-risk projects for long-term growth.")
        ])
    }

    for i in [2, 3, 4]:
        title, text, cards = narratives[i]
        st.markdown(f"<div class='content-section'><div class='section-num'>SECTION {i}</div><div class='section-title'>{title}</div><div class='narrative-text'>{text}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for j, (ct, ctx) in enumerate(cards):
            cols[j].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAPPING & FILTERS ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_region = st.selectbox("Filter Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana":
        filtered_df = filtered_df[filtered_df['Region'] == selected_region]
        
    with f_col2:
        selected_parish = st.selectbox("Filter Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region":
        filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
        
    with f_col3: selected_asset_type = st.selectbox("Filter Anchor Type", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()))

    c5a, c5b = st.columns([0.6, 0.4], gap="large") 
    with c5a:
        f5 = render_map_go(filtered_df)
        s5 = st.plotly_chart(f5, use_container_width=True, on_select="rerun", key="map5")
        if s5 and "selection" in s5 and s5["selection"]["points"]:
            new_id = str(s5["selection"]["points"][0]["location"])
            if st.session_state["active_tract"] != new_id:
                st.session_state["active_tract"] = new_id
                st.rerun()

    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>ANCHOR ASSETS NEAR {curr if curr else '...'}</p>", unsafe_allow_html=True)
        list_html = ""
        if curr and curr in tract_centers:
            lon, lat = tract_centers[curr]
            working_anchors = anchors_df.copy()
            if selected_asset_type != "All Assets":
                working_anchors = working_anchors[working_anchors['Type'] == selected_asset_type]
            working_anchors['dist'] = working_anchors.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in working_anchors.sort_values('dist').head(10).iterrows():
                list_html += f"<div style='background:#111827; border:1px solid #1e293b; padding:10px; border-radius:8px; margin-bottom:8px;'><div style='color:#4ade80; font-size:0.6rem; font-weight:900;'>{str(a['Type']).upper()}</div><div style='color:white; font-weight:700;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.7rem;'>{a['dist']:.1f} miles</div></div>"
        components.html(f"<div style='height: 500px; overflow-y: auto;'>{list_html}</div>", height=520)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.6, 0.4], gap="large") 
    with c6a:
        f6 = render_map_go(filtered_df)
        s6 = st.plotly_chart(f6, use_container_width=True, on_select="rerun", key="map6")
        if s6 and "selection" in s6 and s6["selection"]["points"]:
            new_id = str(s6["selection"]["points"][0]["location"])
            if st.session_state["active_tract"] != new_id:
                st.session_state["active_tract"] = new_id
                st.rerun()

    with c6b:
        if st.session_state["active_tract"]:
            row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]].iloc[0]
            st.markdown(f"<div class='tract-header-container'><div style='font-size: 1.8rem; font-weight: 900; color: #4ade80;'>{str(row['Parish']).upper()}</div><div style='color: #94a3b8;'>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
            
            m_cols = [st.columns(3) for _ in range(2)]
            metrics = [(f"{row['Unemployment Rate (%)']}%", "Unemp"), (f"${row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)',0):,.0f}", "MFI"), (row['Metro Status (Metropolitan/Rural)'], "Status")]
            for i, (v, l) in enumerate(metrics):
                m_cols[0][i].markdown(f"<div class='metric-card'><div class='metric-value'>{v}</div><div class='metric-label'>{l}</div></div>", unsafe_allow_html=True)

            cat = st.selectbox("Category", ["Industrial", "Housing", "Retail", "Tech"])
            just = st.text_area("Narrative Justification")
            if st.button("Add Recommendation", use_container_width=True):
                st.session_state["session_recs"].append({"Tract": st.session_state["active_tract"], "Parish": row['Parish'], "Category": cat, "Justification": just})
                st.rerun()
        else:
            st.info("Select a tract on either map to begin profiling.")

    # --- SECTION 7: LIST ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 7</div><div class='section-title'>My Recommended Tracts</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True)

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())