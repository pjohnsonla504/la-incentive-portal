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
            background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; 
            height: 100%; min-height: 280px; transition: all 0.3s ease; display: flex; flex-direction: column;
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
        
        # User Instruction: Tracks highlighted green are only those eligible for Opportunity Zone 2.0.
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
                    geom = feature['geometry']
                    coords = geom['coordinates']
                    lons, lats = [], []
                    def process_poly(poly):
                        for ring in poly:
                            for pt in ring:
                                lons.append(pt[0]); lats.append(pt[1])
                    if geom['type'] == 'Polygon': process_poly(coords)
                    else: [process_poly(p) for p in coords]
                    centers[geoid] = [np.mean(lons), np.mean(lats)]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def get_zoom_center(geoids):
        # Default view for whole state
        default_center = {"lat": 30.9, "lon": -91.8}
        default_zoom = 6.0
        
        if not geoids or not gj: return default_center, default_zoom
        
        all_lats, all_lons = [], []
        for feature in gj['features']:
            gid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
            if gid in geoids:
                geom = feature['geometry']
                coords = geom['coordinates']
                def collect(poly):
                    for ring in poly:
                        for pt in ring:
                            all_lons.append(pt[0]); all_lats.append(pt[1])
                if geom['type'] == 'Polygon': collect(coords)
                else: [collect(p) for p in coords]
        
        if not all_lats: return default_center, default_zoom
        
        min_lat, max_lat = min(all_lats), max(all_lats)
        min_lon, max_lon = min(all_lons), max(all_lons)
        center = {"lat": (min_lat + max_lat) / 2, "lon": (min_lon + max_lon) / 2}
        
        lat_diff = max_lat - min_lat
        lon_diff = max_lon - min_lon
        max_diff = max(lat_diff, lon_diff)
        
        # Calculate zoom based on the boundary size
        if max_diff < 0.001: zoom = 12.5 
        else: zoom = max(6.0, min(13.0, 8.2 - np.log2(max_diff + 0.01)))
        
        return center, zoom

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Census Tract Number'] for rec in st.session_state["session_recs"]]
        
        def get_color_cat(row):
            if row['geoid_str'] in selected_geoids: return 2
            return 1 if row['Eligibility_Status'] == 'Eligible' else 0
            
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        
        # Dynamic zoom to boundaries
        if st.session_state["active_tract"]:
            center, zoom = get_zoom_center([st.session_state["active_tract"]])
        else:
            center, zoom = get_zoom_center(set(map_df['geoid_str'].tolist()))
            
        sel_idx = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist() if st.session_state["active_tract"] else []
        
        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'], z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], zmin=0, zmax=2,
            showscale=False, marker=dict(opacity=0.7, line=dict(width=0.5, color='white')),
            selectedpoints=sel_idx, hoverinfo="location"
        ))
        
        fig.update_layout(
            mapbox=dict(
                style="carto-positron", 
                zoom=zoom, 
                center=center,
                scrollzoom=True # User requested scroll zoom
            ),
            margin={"r":0,"t":0,"l":0,"b":0}, 
            paper_bgcolor='rgba(0,0,0,0)',
            height=600, 
            clickmode='event+select', 
            uirevision=str(center) # Keeps zoom level stable during interaction
        )
        return fig

    # --- SECTION 1: HERO ---
    st.markdown("""
    <div class='content-section'>
        <div class='section-num'>SECTION 1</div>
        <div style='color: #4ade80; font-weight: 700; text-transform: uppercase; margin-bottom: 10px;'>Opportunity Zones 2.0</div>
        <div class='hero-title'>Louisiana OZ 2.0 Portal</div>
        <div class='narrative-text'>
        The Opportunity Zones Program is a federal capital gains tax incentive program and is designed to drive long-term investments to low-income communities. The law provides a federal tax incentive for investors to re-invest their capital gains into Opportunity Funds, which are specialized vehicles dedicated to investing in designated low-income areas. Federal bill H.R. 1 (OBBBA) signed into law July 2025 will strengthen the program and make the tax incentive permanent.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # --- SECTION 2: BENEFITS ---
    st.markdown("""
    <div class='content-section'>
        <div class='section-num'>SECTION 2</div>
        <div class='section-title'>The Benefit Framework</div>
        <div class='narrative-text'>
            Opportunity Zones encourage investment by providing a series of capital gains tax incentives for qualifying activities in designated areas.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    b_col1, b_col2, b_col3 = st.columns(3)
    with b_col1:
        st.markdown("<div class='benefit-card'><h3>Capital Gain Deferral</h3><p>The OZ 2.0 policy is more flexible for investors with a rolling deferral schedule. Starting on the date of the investment, Investors may defer taxes on capital gains that are reinvested in a QOF for up to five years.</p></div>", unsafe_allow_html=True)
    with b_col2:
        st.markdown("<div class='benefit-card'><h3>Basis Step-Up</h3><p>For gains held in a Qualified Opportunity Fund (QOF) for at least 5 years, investors receive a 10% increase in their investment basis (urban). For Qualified Rural Opportunity Funds (QROF), investors receive a 30% increase.</p></div>", unsafe_allow_html=True)
    with b_col3:
        st.markdown("<div class='benefit-card'><h3>10-Year Gain Exclusion</h3><p>If the investment is held for at least 10 years, new capital gains generated from the sale of a QOZ investment are permanently excluded from taxable income.</p></div>", unsafe_allow_html=True)

    # --- SECTION 3: ADVOCACY ---
    st.markdown("""
    <div class='content-section'>
        <div class='section-num'>SECTION 3</div>
        <div class='section-title'>Strategic Tract Advocacy</div>
        <div class='narrative-text'>
            The most effective OZ selections combine community need, investment readiness, and policy alignment.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    a_col1, a_col2, a_col3 = st.columns(3)
    with a_col1:
        st.markdown("<div class='benefit-card'><h3>Geographical Diversity</h3><p>Ensuring that Opportunity Zone benefits reach both urban centers and rural parishes across all regions of Louisiana.</p></div>", unsafe_allow_html=True)
    with a_col2:
        st.markdown("<div class='benefit-card'><h3>Market Assessment</h3><p>Focusing on areas that have a reasonable chance to attract private capital and put it to productive use within policy timelines.</p></div>", unsafe_allow_html=True)
    with a_col3:
        st.markdown("<div class='benefit-card'><h3>Anchor Density</h3><p>Targeting tracts within a 5-mile radius of major economic drivers, universities, or industrial hubs to ensure project viability.</p></div>", unsafe_allow_html=True)

    # --- SECTION 4: BEST PRACTICES ---
    st.markdown("""
    <div class='content-section'>
        <div class='section-num'>SECTION 4</div>
        <div class='section-title'>National Best Practices</div>
        <div class='narrative-text'>
            Louisiana's framework is built upon successful models and guidance from leading economic policy thinktanks.
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    p_col1, p_col2, p_col3 = st.columns(3)
    with p_col1:
        st.markdown("<div class='benefit-card'><h3>Economic Innovation Group</h3><p>This guide defines successful OZ designation strategies around eight core principles.</p><a href='https://eig.org/ozs-guidance/' target='_blank'>A Guide for Governors ↗</a></div>", unsafe_allow_html=True)
    with p_col2:
        st.markdown("<div class='benefit-card'><h3>Frost Brown Todd</h3><p>Craft a strategy that supports diverse project types, including commercial, industrial, and mixed-use developments.</p><a href='https://fbtgibbons.com/strategic-selection-of-opportunity-zones-2-0-a-governors-guide-to-best-practices/' target='_blank'>Strategic Selection Guide ↗</a></div>", unsafe_allow_html=True)
    with p_col3:
        st.markdown("<div class='benefit-card'><h3>America First Policy Institute</h3><p>Aligning with state-level blueprints for revitalizing American communities through reform.</p><a href='https://www.americafirstpolicy.com/issues/from-policy-to-practice-opportunity-zones-2.0-reforms-and-a-state-blueprint-for-impact' target='_blank'>State Blueprint for Impact ↗</a></div>", unsafe_allow_html=True)

    # --- SECTION 5: MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Opportunity Zone Mapping & Recommendation</div>", unsafe_allow_html=True)
    st.markdown("<div class='narrative-text'>Explore your region or parish with the filters above the map. Census tracts highlighted green are eligible for OZ 2.0. Select a tract to view a detailed profile and anchor assets.</div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: 
        selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": 
        filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    
    with f_col2: 
        selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    
    if selected_parish != "All in Region": 
        filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    
    with f_col3:
        tract_list = ["Search Tract GEOID..."] + sorted(filtered_df['geoid_str'].tolist())
        selected_search = st.selectbox("Find Census Tract", tract_list)
        if selected_search != "Search Tract GEOID...": 
            st.session_state["active_tract"] = selected_search

    # Use a container to prevent layout jumping
    map_container = st.container()
    with map_container:
        combined_map = st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="combined_map")
        
        # Handle manual map selection
        if combined_map and "selection" in combined_map and combined_map["selection"]["points"]:
            new_id = str(combined_map["selection"]["points"][0]["location"])
            if st.session_state["active_tract"] != new_id:
                st.session_state["active_tract"] = new_id
                st.rerun()

    # --- SECTION 6: DATA DISPLAY & LOGIC ---
    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        # Ensure the tract exists in current filtered context
        if curr in master_df["geoid_str"].values:
            row = master_df[master_df["geoid_str"] == curr].iloc[0]
            st.markdown(f"<div style='display: flex; justify-content: space-between; align-items: center; background: #111827; padding: 20px; border-radius: 8px; border: 1px solid #1e293b; margin-bottom: 20px;'><div><div style='font-size: 1.8rem; font-weight: 900; color: #4ade80;'>{str(row['Parish']).upper()}</div><div style='color: #94a3b8; font-size: 0.85rem;'>GEOID: {curr}</div></div><div style='text-align: right;'><div style='font-size: 1.6rem; font-weight: 900; color: #f8fafc;'>{safe_int(row.get('Estimate!!Total!!Population for whom poverty status is determined', 0)):,}</div><div style='color: #94a3b8; font-size: 0.7rem; text-transform: uppercase;'>Population</div></div></div>", unsafe_allow_html=True)
            
            d_col1, d_col2 = st.columns([0.6, 0.4], gap="large")
            with d_col1:
                st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem; letter-spacing:0.15em; margin-bottom:15px;'>TRACT DEMOGRAPHICS</p>", unsafe_allow_html=True)
                m1 = st.columns(3)
                m1[0].markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)
                is_nmtc = "YES" if row['NMTC_Calculated'] in ["Eligible", "Deep Distress"] else "NO"
                m1[1].markdown(f"<div class='metric-card'><div class='metric-value'>{is_nmtc}</div><div class='metric-label'>NMTC Eligible</div></div>", unsafe_allow_html=True)
                is_deep = "YES" if row['NMTC_Calculated'] == "Deep Distress" else "NO"
                m1[2].markdown(f"<div class='metric-card'><div class='metric-value'>{is_deep}</div><div class='metric-label'>Deep Distress</div></div>", unsafe_allow_html=True)
                
                m2 = st.columns(3)
                m2[0].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
                m2[1].markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>MFI</div></div>", unsafe_allow_html=True)
                m2[2].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
                
                m3 = st.columns(3)
                m3[0].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_int(row.get('Population 18 to 24', 0)):,}</div><div class='metric-label'>Pop 18-24</div></div>", unsafe_allow_html=True)
                m3[1].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_int(row.get('Population 65 years and over', 0)):,}</div><div class='metric-label'>Pop 65+</div></div>", unsafe_allow_html=True)
                m3[2].markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)
                
                justification = st.text_area("Strategic Justification", height=120, key="tract_justification")
                if st.button("Add to Recommendation Report", use_container_width=True, type="primary"):
                    st.session_state["session_recs"].append({"Tract": curr, "Justification": justification})
                    st.toast("Tract Added!"); st.rerun()
            
            with d_col2:
                st.markdown("<p style='color:#4ade80; font-weight:900; font-size:0.75rem; letter-spacing:0.15em; margin-bottom:15px;'>NEARBY ANCHORS</p>", unsafe_allow_html=True)
                selected_asset_type = st.selectbox("Anchor Type Filter", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()), key="anch_filt_v2")
                list_html = ""
                if curr in tract_centers:
                    lon, lat = tract_centers[curr]
                    working = anchors_df.copy()
                    if selected_asset_type != "All Assets": 
                        working = working[working['Type'] == selected_asset_type]
                    working['dist'] = working.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
                    for _, a in working.sort_values('dist').head(15).iterrows():
                        link_btn = f"<a href='{a['Link']}' target='_blank' class='view-site-btn'>VIEW SITE ↗</a>" if pd.notna(a.get('Link')) and str(a['Link']).strip() != "" else ""
                        list_html += f"<div class='anchor-card'><div style='color:#4ade80; font-size:0.7rem; font-weight:900; text-transform:uppercase;'>{str(a['Type'])}</div><div style='color:white; font-weight:800; font-size:1.1rem; line-height:1.2;'>{str(a['Name'])}</div><div style='color:#94a3b8; font-size:0.85rem;'>{a['dist']:.1f} miles</div>{link_btn}</div>"
                components.html(f"<style>body {{ background: transparent; font-family: sans-serif; margin:0; padding:0; }} .anchor-card {{ background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }} .view-site-btn {{ display: block; background-color: #4ade80; color: #0b0f19; padding: 6px 0; border-radius: 4px; text-decoration: none; font-size: 0.7rem; font-weight: 900; text-align: center; margin-top: 8px; border: 1px solid #4ade80; }}</style>{list_html}", height=440, scrolling=True)

    # --- SECTION 6: REPORT ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Recommendation Report</div>", unsafe_allow_html=True)
    if st.session_state["session_recs"]:
        final_recs = []
        for i, entry in enumerate(st.session_state["session_recs"], 1):
            t_id = entry['Tract']
            t_match = master_df[master_df['geoid_str'] == t_id]
            if not t_match.empty:
                t_data = t_match.iloc[0]
                final_recs.append({
                    "Recommendation Count": i,
                    "Census Tract Number": t_id,
                    "Parish": t_data.get('Parish', 'N/A'),
                    "Population": f"{safe_int(t_data.get('Estimate!!Total!!Population for whom poverty status is determined', 0)):,}",
                    "Poverty Rate": f"{safe_float(t_data.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%",
                    "Median Family Income": f"${safe_float(t_data.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}",
                    "Broadband Accessibility": f"{safe_float(t_data.get('Broadband Internet (%)', 0)):.1f}%",
                    "Justification": entry.get('Justification', '')
                })
        
        report_df = pd.DataFrame(final_recs)
        st.dataframe(report_df, use_container_width=True, hide_index=True)
        if st.button("Clear Report"): 
            st.session_state["session_recs"] = []
            st.rerun()
    else: 
        st.info("No tracts selected.")
    
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())