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

# --- 1. LOGIN ---
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
        st.markdown("""
            <style>
            .stApp { background: linear-gradient(135deg, #0b0f19 0%, #1e293b 100%); }
            .login-card {
                background: rgba(255, 255, 255, 0.05);
                backdrop-filter: blur(15px);
                border: 1px solid rgba(255, 255, 255, 0.1);
                padding: 40px;
                border-radius: 24px;
                text-align: center;
                box-shadow: 0 20px 40px rgba(0,0,0,0.4);
            }
            .login-title { font-weight: 900; color: #4ade80; font-size: 2.5rem; margin-bottom: 5px; }
            .login-sub { color: #94a3b8; font-size: 0.9rem; margin-bottom: 30px; }
            </style>
            """, unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 1, 1])
        with col_mid:
            st.markdown("<div class='login-card'><div class='login-title'>OZ 2.0</div><div class='login-sub'>Strategic Investment Infrastructure</div></div>", unsafe_allow_html=True)
            st.text_input("Credential ID", key="username")
            st.text_input("Security Key", type="password", key="password")
            st.button("Authorize Access", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():
    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }

        .anchor-scroll-area {
            height: 440px; 
            overflow-y: auto;
            padding-right: 10px;
        }
        .asset-card { background: #1f2937; border: 1px solid #374151; padding: 12px; border-radius: 10px; margin-bottom: 10px; }
        .asset-link { color: #4ade80 !important; text-decoration: none !important; font-weight: 700; font-size: 0.9rem; }
        
        .metric-box { background: #1f2937; border: 1px solid #374151; padding: 10px; border-radius: 8px; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .m-val { font-size: 1rem; font-weight: 900; color: #4ade80; }
        .m-lab { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }

        .section-title { font-size: 1.8rem; font-weight: 900; margin-bottom: 10px; color: #4ade80; }
        </style>
        """, unsafe_allow_html=True)

    # --- DATA ENGINE ---
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 3956 * 2 * asin(sqrt(a))

    @st.cache_data(ttl=3600)
    def load_data():
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        def read_csv(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)
        
        # Load Opportunity Zones Master File
        master = read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        # Eligibility logic: Green highlights for OZ 2.0
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        
        # Load LA Anchors
        anchors = read_csv("la_anchors.csv")
        
        centers = {}
        if gj:
            for feature in gj['features']:
                props = feature['properties']
                geoid = props.get('GEOID') or props.get('GEOID20')
                try:
                    geom = feature['geometry']
                    if geom['type'] == 'Polygon':
                        pts = np.array(geom['coordinates'][0])
                    else: # MultiPolygon
                        pts = np.array(geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_data()

    # --- COMMAND CENTER ---
    st.markdown("<div class='section-title'>05. Strategic Analysis Command Center</div>", unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1,1,1])
    with f1: s_reg = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    with f2:
        f_df = master_df[master_df['Region'] == s_reg] if s_reg != "All Louisiana" else master_df
        s_par = st.selectbox("Parish", ["All in Region"] + sorted(f_df['Parish'].dropna().unique().tolist()))
    with f3:
        search = st.text_input("GEOID Search", placeholder="11-digit FIPS")
        if search in master_df['geoid_str'].values: st.session_state["active_tract"] = search

    # Map Rendering
    map_df = f_df[f_df['Parish'] == s_par] if s_par != "All in Region" else f_df
    
    # Click interaction simulation via search/selection
    fig = go.Figure(go.Choroplethmapbox(
        geojson=gj, 
        locations=map_df['geoid_str'], 
        z=map_df['Eligibility_Status'].apply(lambda x: 1 if x == 'Eligible' else 0),
        featureidkey="properties.GEOID", 
        colorscale=[[0, '#334155'], [1, '#4ade80']], 
        showscale=False,
        marker=dict(opacity=0.7, line=dict(width=0.5, color='white')),
        hovertemplate="<b>Tract: %{location}</b><br>Status: %{customdata}<extra></extra>",
        customdata=map_df['Eligibility_Status']
    ))
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", zoom=6, center={"lat": 30.9, "lon": -91.8}), 
        margin={"r":0,"t":0,"l":0,"b":0}, 
        height=500
    )
    st.plotly_chart(fig, use_container_width=True)

    # --- THE FIXED DATA METRIC ROW ---
    st.markdown("---")
    curr_id = st.session_state["active_tract"]
    
    col_anc, col_prof, col_rec = st.columns([1.2, 1.5, 1])

    with col_anc:
        st.markdown("#### 📍 Institutional Anchors")
        anc_filter = st.selectbox("Filter by Type", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()))
        
        st.markdown("<div class='anchor-scroll-area'>", unsafe_allow_html=True)
        # We display anchors based on either the selected tract proximity OR general list if none selected
        if curr_id and curr_id in tract_centers:
            lon, lat = tract_centers[curr_id]
            wa = anchors_df.copy()
            if anc_filter != "All Assets": wa = wa[wa['Type'] == anc_filter]
            wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            display_df = wa.sort_values('dist').head(25)
            
            for _, a in display_df.iterrows():
                url = a.get('Link', '')
                link_tag = f"<a href='{url}' target='_blank' class='asset-link'>{a['Name']} ↗</a>" if pd.notna(url) and str(url).strip() != "" else f"<span class='asset-link'>{a['Name']}</span>"
                st.markdown(f"""
                    <div class='asset-card'>
                        <small style='color:#4ade80;'>{a['Type'].upper()}</small><br>
                        {link_tag}<br>
                        <small style='color:#94a3b8;'>{a['dist']:.1f} miles from center</small>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Select a Tract to see nearest anchors.")
            # Default list if no tract selected
            wa = anchors_df.copy()
            if anc_filter != "All Assets": wa = wa[wa['Type'] == anc_filter]
            for _, a in wa.head(10).iterrows():
                st.markdown(f"<div class='asset-card'><small style='color:#4ade80;'>{a['Type'].upper()}</small><br><b>{a['Name']}</b></div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col_prof:
        st.markdown("#### 📊 Census Tract Profile")
        if curr_id:
            row = master_df[master_df["geoid_str"] == curr_id].iloc[0]
            
            # Eligibility Banner
            ebg = "rgba(74,222,128,0.1)" if row['Eligibility_Status'] == 'Eligible' else "rgba(203,213,225,0.1)"
            etxt = "#4ade80" if row['Eligibility_Status'] == 'Eligible' else "#cbd5e1"
            estat = "OZ 2.0 ELIGIBLE" if row['Eligibility_Status'] == 'Eligible' else "INELIGIBLE"
            st.markdown(f"<div style='background:{ebg}; border:1px solid {etxt}; padding:10px; border-radius:8px; text-align:center; color:{etxt}; font-weight:900; margin-bottom:15px;'>{estat}</div>", unsafe_allow_html=True)
            
            # Metrics Grid
            m_grid = [st.columns(3) for _ in range(3)]
            metrics = [
                (f"{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%", "Poverty"),
                (f"${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}", "MFI"),
                (f"{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%", "Unemp."),
                (row.get('Metro Status (Metropolitan/Rural)', 'N/A'), "Metro"),
                (f"{safe_int(row.get('Population 18 to 24', 0)):,}", "Pop 18-24"),
                (f"{safe_int(row.get('Population 65 years and over', 0)):,}", "Pop 65+"),
                (f"{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%", "Broadband"),
                (f"{safe_int(row.get('Total Housing Units', 0)):,}", "Housing"),
                (row.get('NMTC_Calculated', 'Ineligible'), "NMTC")
            ]
            for i, (v, l) in enumerate(metrics):
                m_grid[i//3][i%3].markdown(f"<div class='metric-box'><div class='m-val'>{v}</div><div class='m-lab'>{l}</div></div>", unsafe_allow_html=True)
        else:
            st.info("Input a GEOID or select a region to populate metrics.")

    with col_rec:
        st.markdown("#### ✍️ Investment Thesis")
        cat = st.selectbox("Asset Class", ["Industrial", "Housing", "Retail", "Healthcare", "Infrastructure"])
        just = st.text_area("Justification", height=230, placeholder="Explain the strategic alignment for this specific tract...")
        if st.button("Commit to Report", use_container_width=True, type="primary"):
            if curr_id:
                st.session_state["session_recs"].append({"Tract": curr_id, "Class": cat, "Thesis": just})
                st.toast(f"Tract {curr_id} added to report.")

    # --- FINAL REPORT ---
    if st.session_state["session_recs"]:
        st.markdown("### 06. Generated Investment Pipeline")
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True, hide_index=True)