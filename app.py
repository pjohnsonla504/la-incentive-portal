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
        
        html, body, [class*="stApp"] { 
            font-family: 'Inter', sans-serif !important; 
            background-color: #0b0f19 !important; 
            color: #ffffff; 
        }

        div[data-baseweb="select"] > div {
            background-color: #ffffff !important;
            border: 1px solid #cbd5e1 !important;
            border-radius: 6px !important;
        }
        div[data-baseweb="select"] * {
            color: #0f172a !important;
        }
        label[data-testid="stWidgetLabel"] { 
            color: #94a3b8 !important; 
            font-weight: 700 !important; 
            text-transform: uppercase; 
            font-size: 0.75rem !important; 
            letter-spacing: 0.05em;
        }

        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; margin-bottom: 20px; line-height: 1.1; }
        .narrative-text { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; max-width: 900px; margin-bottom: 30px; }
        
        [data-testid="stHorizontalBlock"] { align-items: stretch; display: flex; flex-direction: row; }
        [data-testid="stColumn"] { display: flex; }
        [data-testid="stColumn"] > div { flex: 1; display: flex; flex-direction: column; }

        .benefit-card { 
            background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; 
            border-radius: 12px; height: 100%; min-height: 280px; transition: all 0.3s ease; 
            display: flex; flex-direction: column; 
        }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 15px; font-weight: 800; font-size: 1.3rem; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; flex-grow: 1; }
        .benefit-card a { color: #4ade80; text-decoration: none; font-weight: 700; margin-top: 15px; }
        
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        
        .anchor-card { background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }
        .view-site-btn { 
            display: block; background-color: #4ade80; color: #0b0f19 !important; 
            padding: 6px 0; border-radius: 4px; text-decoration: none !important; 
            font-size: 0.7rem; font-weight: 900; text-align: center; margin-top: 8px; border: 1px solid #4ade80;
        }
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
        def read_csv_with_fallback(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)

        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )

        pov_col = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
        mfi_ratio_col = "Percentage of Benchmarked Median Family Income" 
        unemp_ratio_col = "Unemployment Ratio" 

        def calc_nmtc_status(row):
            pov = safe_float(row.get(pov_col, 0))
            mfi_pct = safe_float(row.get(mfi_ratio_col, 0)) if mfi_ratio_col in row else 100
            unemp_ratio = safe_float(row.get(unemp_ratio_col, 0)) if unemp_ratio_col in row else 1.0
            if pov > 40 or mfi_pct <= 40 or unemp_ratio >= 2.5: return "Deep Distress"
            elif pov >= 20 or mfi_pct <= 80 or unemp_ratio >= 1.5: return "Eligible"
            return "Ineligible"

        master['NMTC_Calculated'] = master.apply(calc_nmtc_status, axis=1)
        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    coords = feature['geometry']['coordinates'][0]
                    if feature['geometry']['type'] == 'MultiPolygon': coords = coords[0]
                    pts = np.array(coords)
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Census Tract Number'] for rec in st.session_state["session_recs"]]
        def get_color_cat(row):
            if row['geoid_str'] in selected_geoids: return 2
            return 1 if row['Eligibility_Status'] == 'Eligible' else 0
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        center = {"lat": 30.9, "lon": -91.8}
        zoom = 6.0
        sel_idx = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist() if st.session_state["active_tract"] else []
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], zmin=0, zmax=2,
            showscale=False, marker=dict(opacity=0.7, line=dict(width=0.5, color='white')),
            selectedpoints=sel_idx, hoverinfo="location"
        ))
        fig.update_layout(mapbox=dict(style="carto-positron", zoom=zoom, center=center),
                          margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)',
                          height=600, clickmode='event+select', uirevision='constant')
        return fig

    # --- SECTIONS 1-4 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-title'>Louisiana OZ 2.0 Portal</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Benefit Framework</div></div>", unsafe_allow_html=True)
    b_cols = st.columns(3)
    with b_cols[0]: st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>Defer taxes on capital gains for up to five years.</p></div>", unsafe_allow_html=True)
    with b_cols[1]: st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>10% step-up for Urban QOFs, 30% for Rural QROFs after 5 years.</p></div>", unsafe_allow_html=True)
    with b_cols[2]: st.markdown("<div class='benefit-card'><h3>10-Year Gain Exclusion</h3><p>Permanent exclusion from capital gains taxes after 10 years.</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Strategic Tract Advocacy</div></div>", unsafe_allow_html=True)
    a_cols = st.columns(3)
    with a_cols[0]: st.markdown("<div class='benefit-card'><h3>Geographical Diversity</h3><p>Balance between urban and rural designations.</p></div>", unsafe_allow_html=True)
    with a_cols[1]: st.markdown("<div class='benefit-card'><h3>Market Assessment</h3><p>High potential for private capital attraction.</p></div>", unsafe_allow_html=True)
    with a_cols[2]: st.markdown("<div class='benefit-card'><h3>Anchor Density</h3><p>Focus near economic drivers.</p></div>", unsafe_allow_html=True)

    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>National Best Practices</div></div>", unsafe_allow_html=True)
    p_cols = st.columns(3)
    with p_cols[0]: st.markdown("<div class='benefit-card'><h3>EIG</h3><p>Economic Innovation Group guidance.</p><a href='#'>Link ↗</a></div>", unsafe_allow_html=True)
    with p_cols[1]: st.markdown("<div class='benefit-card'><h3>Frost Brown Todd</h3><p>Diverse project type strategies.</p><a href='#'>Link ↗</a></div>", unsafe_allow_html=True)
    with p_cols[2]: st.markdown("<div class='benefit-card'><h3>AFPI</h3><p>State blueprint for impact.</p><a href='#'>Link ↗</a></div>", unsafe_allow_html=True)

    # --- SECTION 5: MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping</div></div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    with f_col2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    with f_col3:
        tract_list = ["Search Tract GEOID..."] + sorted(filtered_df['geoid_str'].tolist())
        selected_search = st.selectbox("Find Census Tract", tract_list)
        if selected_search != "Search Tract GEOID...": st.session_state["active_tract"] = selected_search

    combined_map = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="combined_map")
    if combined_map and "selection" in combined_map and combined_map["selection"]["points"]:
        new_id = str(combined_map["selection"]["points"][0]["location"])
        if st.session_state["active_tract"] != new_id:
            st.session_state["active_tract"] = new_id
            st.rerun()

    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == curr].iloc[0]
        
        # Pulling variables for Report
        pop = safe_int(row.get('Estimate!!Total!!Population for whom poverty status is determined', 0))
        metro = row.get('Metro Status (Metropolitan/Rural)', 'N/A')
        pov = f"{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%"
        mfi = f"${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}"

        st.markdown(f"### {str(row['Parish']).upper()} - {curr}")
        d_col1, d_col2 = st.columns([0.6, 0.4], gap="large")
        with d_col1:
            st.markdown("<p style='color:#4ade80; font-weight:900;'>TRACT DEMOGRAPHICS</p>", unsafe_allow_html=True)
            # Display metrics...
            justification = st.text_area("Strategic Justification", height=120, key="tract_justification")
            if st.button("Add to Recommendation Report", use_container_width=True, type="primary"):
                st.session_state["session_recs"].append({
                    "Tract Recommendation Count": len(st.session_state["session_recs"]) + 1,
                    "Census Tract Number": curr,
                    "Parish": row['Parish'],
                    "Population": pop,
                    "Metro Status": metro,
                    "Poverty Rate": pov,
                    "Median Family Income": mfi,
                    "Strategic Justification": justification
                })
                st.toast("Tract Added!"); st.rerun()
        with d_col2:
            st.markdown("<p style='color:#4ade80; font-weight:900;'>NEARBY ANCHORS</p>", unsafe_allow_html=True)
            # Anchor list logic...

    # --- SECTION 6: REPORT ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        report_df = pd.DataFrame(st.session_state["session_recs"])
        
        # Displaying with exact requested column order
        cols_ordered = [
            "Tract Recommendation Count", "Census Tract Number", "Parish", 
            "Population", "Metro Status", "Poverty Rate", 
            "Median Family Income", "Strategic Justification"
        ]
        st.dataframe(report_df[cols_ordered], use_container_width=True, hide_index=True)
        
        c1, c2 = st.columns(2)
        with c1:
            csv = report_df[cols_ordered].to_csv(index=False).encode('utf-8')
            st.download_button("Download Report CSV", data=csv, file_name="OZ_Recommendation_Report.csv", mime="text/csv", use_container_width=True)
        with c2:
            if st.button("Clear Report", use_container_width=True): 
                st.session_state["session_recs"] = []
                st.rerun()
    else:
        st.info("No tracts selected for recommendation.")
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())