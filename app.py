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
if "username" not in st.session_state:
    st.session_state["username"] = ""

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

# --- 1. PERSISTENCE ENGINE ---
def load_user_recs(username):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        recs_df = conn.read(worksheet="Recommendations", ttl=0) 
        if recs_df.empty: return []
        return recs_df[recs_df['username'] == username].to_dict('records')
    except: return []

def save_rec_to_cloud(rec_entry):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        rec_entry['username'] = st.session_state["username"]
        existing_df = conn.read(worksheet="Recommendations", ttl=0)
        new_row = pd.DataFrame([rec_entry])
        updated_df = pd.concat([existing_df, new_row], ignore_index=True) if not existing_df.empty else new_row
        conn.update(worksheet="Recommendations", data=updated_df)
    except Exception as e:
        st.error(f"Cloud Save Failed: {e}")

# --- 2. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username_input"].strip()
            p = str(st.session_state["password_input"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = u
                    st.session_state["session_recs"] = load_user_recs(u)
                    return
            st.session_state["password_correct"] = False
            st.error("Invalid credentials")
        except Exception as e: st.error(f"Auth Error: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("<style>.stApp { background-color: #0b0f19 !important; }</style>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<h1 style='color: white; text-align:center;'>OZ 2.0 Portal</h1>", unsafe_allow_html=True)
            st.text_input("Username", key="username_input")
            st.text_input("Password", type="password", key="password_input")
            st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 3. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .nav-link:hover { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .benefit-card { background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; transition: all 0.3s ease; }
        .benefit-card:hover { border-color: #4ade80 !important; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        .anchor-card { background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }
        .view-site-btn { display: block; background-color: #4ade80; color: #0b0f19 !important; padding: 8px 0; border-radius: 4px; text-decoration: none !important; font-size: 0.75rem; font-weight: 900; text-align: center; margin-top: 10px; border: 1px solid #4ade80; }
        </style>
        <div class="nav-container">
            <a class="nav-link" href="#section-1">Overview</a><a class="nav-link" href="#section-2">Benefits</a><a class="nav-link" href="#section-3">Strategy</a><a class="nav-link" href="#section-4">Best Practices</a><a class="nav-link" href="#section-5">Mapping</a><a class="nav-link" href="#section-6">Report</a>
        </div>
    """, unsafe_allow_html=True)

    # --- 4. DATA ENGINE ---
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
        def read_csv(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)
        master = read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1', 'true'] else 'Ineligible')
        
        def calc_nmtc(row):
            pov, mfi = safe_float(row.get("Estimate!!Percent below poverty level!!Population for whom poverty status is determined", 0)), safe_float(row.get("Percentage of Benchmarked Median Family Income", 0))
            unemp = safe_float(row.get("Unemployment Ratio", 0))
            if pov > 40 or mfi <= 40 or unemp >= 2.5: return "Deep Distress"
            elif pov >= 20 or mfi <= 80 or unemp >= 1.5: return "Eligible"
            return "Ineligible"
        master['NMTC_Calculated'] = master.apply(calc_nmtc, axis=1)
        anchors = read_csv("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for f in gj['features']:
                gid = f['properties'].get('GEOID') or f['properties'].get('GEOID20')
                try:
                    pts = np.array(f['geometry']['coordinates'][0] if f['geometry']['type'] == 'Polygon' else f['geometry']['coordinates'][0][0])
                    centers[gid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        sel_recs = [str(r['Tract']) for r in st.session_state["session_recs"]]
        map_df['Color_Category'] = map_df.apply(lambda r: 2 if str(r['geoid_str']) in sel_recs else (1 if r['Eligibility_Status'] == 'Eligible' else 0), axis=1)
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], zmin=0, zmax=2, showscale=False,
            marker=dict(opacity=0.6, line=dict(width=1, color='black'))
        ))
        fig.update_layout(mapbox=dict(style="carto-positron", zoom=6, center={"lat": 30.9, "lon": -91.8}), margin={"r":0,"t":0,"l":0,"b":0}, height=600)
        return fig

    # --- SECTIONS 1-4 (Narrative) ---
    st.markdown("<div id='section-1' class='content-section'><div class='section-num'>SECTION 1</div><h1 class='section-title'>Louisiana OZ 2.0 Portal</h1><p>The Opportunity Zones Program drive long-term investments to low-income communities via H.R. 1 (OBBBA).</p></div>", unsafe_allow_html=True)
    
    # --- SECTION 5: MAPPING & TRACT DETAILS ---
    st.markdown("<div id='section-5' class='content-section'><div class='section-num'>SECTION 5</div><h2 class='section-title'>Strategic Mapping</h2></div>", unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns(3)
    reg = c1.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered = master_df.copy()
    if reg != "All Louisiana": filtered = filtered[filtered['Region'] == reg]
    par = c2.selectbox("Parish", ["All in Region"] + sorted(filtered['Parish'].dropna().unique().tolist()))
    if par != "All in Region": filtered = filtered[filtered['Parish'] == par]
    tract_id = c3.selectbox("Find Tract", ["Search..."] + sorted(filtered['geoid_str'].tolist()))
    if tract_id != "Search...": st.session_state["active_tract"] = tract_id

    st.plotly_chart(render_map_go(filtered), use_container_width=True)

    if st.session_state["active_tract"]:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]].iloc[0]
        st.markdown(f"### {row['Parish'].upper()} - {st.session_state['active_tract']}")
        
        d_col1, d_col2 = st.columns([0.6, 0.4], gap="large")
        with d_col1:
            st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem;'>TRACT DEMOGRAPHICS (9 METRICS)</p>", unsafe_allow_html=True)
            # Row 1
            m1, m2, m3 = st.columns(3)
            m1.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_int(row.get('Estimate!!Total!!Population for whom poverty status is determined', 0)):,}</div><div class='metric-label'>Total Population</div></div>", unsafe_allow_html=True)
            m2.markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
            m3.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['NMTC_Calculated'] in ['Eligible', 'Deep Distress'] else 'NO'}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
            # Row 2
            m4, m5, m6 = st.columns(3)
            m4.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if row['NMTC_Calculated'] == 'Deep Distress' else 'NO'}</div><div class='metric-label'>Deep Distress</div></div>", unsafe_allow_html=True)
            m5.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
            m6.markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>Median Family Income</div></div>", unsafe_allow_html=True)
            # Row 3
            m7, m8, m9 = st.columns(3)
            m7.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            m8.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_int(row.get('Population 18 to 24', 0)):,} / {safe_int(row.get('Population 65 years and over', 0)):,}</div><div class='metric-label'>Pop 18-24 / 65+</div></div>", unsafe_allow_html=True)
            m9.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%</div><div class='metric-label'>Broadband Coverage</div></div>", unsafe_allow_html=True)
            
            cat = st.selectbox("Category", ["Housing", "Business", "Tech", "Healthcare"])
            just = st.text_area("Justification")
            if st.button("Add to Report"):
                new_e = {"Tract": st.session_state["active_tract"], "Parish": row['Parish'], "Category": cat, "Justification": just}
                st.session_state["session_recs"].append(new_e)
                save_rec_to_cloud(new_e)
                st.toast("Saved!"); st.rerun()

        with d_col2:
            st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem;'>NEARBY ANCHORS</p>", unsafe_allow_html=True)
            if st.session_state["active_tract"] in tract_centers:
                lon, lat = tract_centers[st.session_state["active_tract"]]
                working = anchors_df.copy()
                working['dist'] = working.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                for _, a in working.sort_values('dist').head(4).iterrows():
                    st.markdown(f"""
                        <div class='anchor-card'>
                            <div style='display:flex; justify-content:space-between;'>
                                <span style='color:#f8fafc; font-weight:800; font-size:0.85rem;'>{a['Name']}</span>
                                <span style='color:#4ade80; font-size:0.7rem;'>{a['dist']:.1f} mi</span>
                            </div>
                            <div style='color:#94a3b8; font-size:0.7rem; margin-top:4px;'>{a['Type']}</div>
                            <a href='{a.get('URL', '#')}' target='_blank' class='view-site-btn'>View Site Details</a>
                        </div>
                    """, unsafe_allow_html=True)

    # --- SECTION 6: REPORT ---
    st.markdown("<div id='section-6' class='content-section'><h2>Recommendation Report</h2></div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True)