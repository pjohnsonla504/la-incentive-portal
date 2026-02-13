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
    st.session_state["active_tract"] = "22071001700" 
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
        except Exception:
            st.session_state["password_correct"] = False

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            .login-card { max-width: 360px; margin: 100px auto; padding: 30px; background: #111827; border: 1px solid #1e293b; border-top: 4px solid #4ade80; border-radius: 12px; text-align: center; font-family: 'Inter', sans-serif; }
            </style>
            <div class="login-card"><h2 style='color:white;'>OZ 2.0 Portal</h2><p style='color:#94a3b8;'>Stakeholder Access</p></div>
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
        .content-section { padding: 50px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; text-transform: uppercase; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; color: #f8fafc; }
        .hero-title { font-size: 3.5rem; font-weight: 900; color: #f8fafc; line-height: 1.1; margin-bottom: 20px; }
        .narrative-text { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background-color: #111827 !important; padding: 25px; border: 1px solid #1e293b; border-radius: 8px; min-height: 200px; transition: 0.3s; }
        .benefit-card:hover { border-color: #4ade80; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 100px; display: flex; flex-direction: column; justify-content: center; }
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; margin-top: 5px; }
        .tract-header-container { background-color: #111827; padding: 20px; border-radius: 10px; border-top: 4px solid #4ade80; border: 1px solid #1e293b; margin-bottom: 20px; }
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
        poverty_col = 'Estimate!!Percent below poverty level!!Population for whom poverty status is determined'
        unemployment_col = 'Unemployment Rate (%)'
        mfi_col = 'Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)'
        
        def clean_num(s):
            try: return float(str(s).replace('%','').replace('$','').replace(',','').strip())
            except: return 0.0

        master['_pov'] = master[poverty_col].apply(clean_num)
        master['_unemp'] = master[unemployment_col].apply(clean_num)
        master['_mfi'] = master[mfi_col].apply(clean_num)

        # PolicyMap Distress Benchmarks
        NAT_UNEMP, STATE_MFI = 5.3, 86934 
        master['NMTC_Eligible'] = ((master['_pov'] >= 20) | (master['_mfi'] <= (0.8 * STATE_MFI))).map({True:'Yes', False:'No'})
        master['Severe_Distress'] = ((master['_pov'] >= 30) | (master['_mfi'] <= (0.6 * STATE_MFI)) | (master['_unemp'] >= (1.5 * NAT_UNEMP))).map({True:'Yes', False:'No'})
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
                    coords = f['geometry']['coordinates'][0]
                    if f['geometry']['type'] == 'MultiPolygon': coords = coords[0]
                    c = np.array(coords)
                    centers[gid] = [np.mean(c[:, 0]), np.mean(c[:, 1])]
                except: pass
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map(df, is_filtered=False, height=600):
        center = {"lat": 30.8, "lon": -91.8}
        zoom = 6.2
        if is_filtered and not df.empty:
            ids = df['geoid_str'].tolist()
            subs = [tract_centers[gid] for gid in ids if gid in tract_centers]
            if subs:
                lons, lats = zip(*subs)
                center, zoom = {"lat": np.mean(lats), "lon": np.mean(lons)}, 8.5

        fig = px.choropleth_mapbox(df, geojson=gj, locations="geoid_str", 
                                     featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
                                     color="Eligibility_Status", 
                                     color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#1e293b"},
                                     mapbox_style="carto-positron", zoom=zoom, center=center, opacity=0.5)
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height)
        return fig

    # --- SECTION 1-4: NARRATIVE RESTORED ---
    st.markdown("""
        <div class='content-section'>
            <div class='section-num'>Section 1</div>
            <div class='hero-title'>Louisiana Opportunity Zone 2.0 Portal</div>
            <p class='narrative-text'>Advancing economic resilience through strategic investment. This portal identifies high-impact census tracts eligible for the 2.0 framework.</p>
        </div>
    """, unsafe_allow_html=True)
    
    c2 = st.columns(3)
    c2[0].markdown("<div class='benefit-card'><h3>Tax Deferral</h3><p>Defer capital gains through 2026/27.</p></div>", unsafe_allow_html=True)
    c2[1].markdown("<div class='benefit-card'><h3>Step-Up Basis</h3><p>10-30% reduction in tax liability.</p></div>", unsafe_allow_html=True)
    c2[2].markdown("<div class='benefit-card'><h3>Tax Free Exit</h3><p>Zero tax on appreciation after 10 years.</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: FILTERED ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>Section 5</div><div class='section-title'>Strategic Asset Mapping</div></div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        sel_region = st.selectbox("Region Filter", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    with f_col2:
        par_opts = master_df[master_df['Region'] == sel_region]['Parish'] if sel_region != "All Louisiana" else master_df['Parish']
        sel_parish = st.selectbox("Parish Filter", ["All Parishes"] + sorted(par_opts.dropna().unique().tolist()))
    with f_col3:
        sel_asset = st.selectbox("Anchor Type", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()))

    filtered_master = master_df.copy()
    filter_active = False
    if sel_region != "All Louisiana": 
        filtered_master = filtered_master[filtered_master['Region'] == sel_region]
        filter_active = True
    if sel_parish != "All Parishes": 
        filtered_master = filtered_master[filtered_master['Parish'] == sel_parish]
        filter_active = True

    c5a, c5b = st.columns([0.6, 0.4], gap="large")
    with c5a:
        st.plotly_chart(render_map(filtered_master, is_filtered=filter_active), use_container_width=True, on_select="rerun", key="map5")
        if st.session_state.get("map5") and st.session_state["map5"]["selection"]["points"]:
            st.session_state["active_tract"] = str(st.session_state["map5"]["selection"]["points"][0]["location"])

    with c5b:
        curr = st.session_state["active_tract"]
        st.markdown(f"<p style='color:#94a3b8; font-weight:800;'>LOCAL ASSETS NEAR {curr}</p>", unsafe_allow_html=True)
        list_html = ""
        if curr in tract_centers:
            lon, lat = tract_centers[curr]
            f_anchors = anchors_df.copy()
            if sel_asset != "All Assets": f_anchors = f_anchors[f_anchors['Type'] == sel_asset]
            f_anchors['dist'] = f_anchors.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in f_anchors.sort_values('dist').head(10).iterrows():
                btn = f"<div style='margin-top:8px;'><a href='{a['Link']}' target='_blank' style='background:#4ade80; color:#0b0f19; padding:4px 10px; border-radius:4px; font-size:0.7rem; font-weight:900; text-decoration:none;'>VIEW SITE 🔗</a></div>" if a['Type'] in ['Land','Buildings'] and str(a['Link']).strip() else ""
                list_html += f"<div style='background:#111827; border:1px solid #1e293b; padding:12px; border-radius:8px; margin-bottom:10px;'><div style='color:#4ade80; font-size:0.6rem; font-weight:900;'>{str(a['Type']).upper()}</div><div style='font-weight:700; color:white;'>{a['Name']}</div><div style='color:#94a3b8; font-size:0.7rem;'>📍 {a['dist']:.1f} miles away</div>{btn}</div>"
        components.html(f"<div style='height:500px; overflow-y:auto;'>{list_html}</div>", height=520)

    # --- SECTION 6: PROFILING GRID (LINKED TO FILTERS) ---
    st.markdown("<div class='content-section'><div class='section-num'>Section 6</div><div class='section-title'>Tract Profiling</div></div>", unsafe_allow_html=True)
    c6a, c6b = st.columns([0.45, 0.55])
    with c6a:
        st.plotly_chart(render_map(filtered_master, is_filtered=filter_active, height=750), use_container_width=True, on_select="rerun", key="map6")
        if st.session_state.get("map6") and st.session_state["map6"]["selection"]["points"]:
            st.session_state["active_tract"] = str(st.session_state["map6"]["selection"]["points"][0]["location"])

    with c6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            st.markdown(f"<div class='tract-header-container'><div style='font-size:1.8rem; font-weight:900; color:#4ade80;'>{str(d.get('Parish','')).upper()}</div><div>TRACT: {st.session_state['active_tract']}</div></div>", unsafe_allow_html=True)
            m_cols = [st.columns(3) for _ in range(3)]
            metrics = [
                (d['NMTC_Eligible'], "NMTC Eligible"), (d['Severe_Distress'], "Severe Distress"), (d['Deep_Distress'], "Deep Distress"),
                (f"{d['_pov']:.1f}%", "Poverty Rate"), (f"{d['_unemp']:.1f}%", "Unemployment"), (f"${d['_mfi']:,.0f}", "Median Income"),
                (d.get('Broadband Internet (%)','0%'), "Broadband"), (d.get('Metro Status (Metropolitan/Rural)','N/A'), "Status"), (d.get('Parish','N/A'), "Parish")
            ]
            for i, (val, lbl) in enumerate(metrics):
                m_cols[i//3][i%3].markdown(f"<div class='metric-card'><div class='metric-value'>{val}</div><div class='metric-label'>{lbl}</div></div>", unsafe_allow_html=True)

            cat = st.selectbox("Category", ["Industrial Development", "Workforce Housing", "Rural Broadband", "Technology Hub"])
            just = st.text_area("Narrative Justification")
            if st.button("Add to Recommendations", type="primary", use_container_width=True):
                st.session_state["session_recs"].append({"Date": datetime.now().strftime("%I:%M %p"), "Tract": st.session_state["active_tract"], "Parish": d.get('Parish'), "Category": cat, "Justification": just})

    # --- SECTION 7: SUMMARY & DOWNLOAD ---
    st.markdown("<div class='content-section'><div class='section-num'>Section 7</div><div class='section-title'>Session Summary</div></div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        df_recs = pd.DataFrame(st.session_state["session_recs"])
        st.dataframe(df_recs, use_container_width=True, hide_index=True)
        csv = df_recs.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV Export", data=csv, file_name=f"OZ_Recs_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
        if st.button("Clear List"): st.session_state["session_recs"] = []; st.rerun()

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())