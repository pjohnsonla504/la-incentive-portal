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

        /* Sidebar Navigation */
        [data-testid="stSidebar"] { background-color: #0f172a !important; border-right: 1px solid #1e293b; }
        .toc-header { color: #4ade80; font-size: 0.75rem; font-weight: 900; letter-spacing: 0.1em; margin-bottom: 15px; text-transform: uppercase; padding: 0 10px; }
        .toc-link { display: block; padding: 10px; color: #94a3b8 !important; text-decoration: none; font-weight: 600; font-size: 0.85rem; border-radius: 5px; margin-bottom: 5px; transition: 0.2s; }
        .toc-link:hover { background-color: #1e293b; color: #4ade80 !important; }

        /* Anchor Asset Scroll Area - The "Red Oval" Area */
        .anchor-scroll-container {
            height: 480px; 
            overflow-y: auto;
            padding-right: 12px;
            scrollbar-width: thin;
            scrollbar-color: #4ade80 #1f2937;
        }
        /* Custom Scrollbar for Chrome/Safari/Edge */
        .anchor-scroll-container::-webkit-scrollbar { width: 8px; }
        .anchor-scroll-container::-webkit-scrollbar-track { background: #1f2937; border-radius: 10px; }
        .anchor-scroll-container::-webkit-scrollbar-thumb { background: #4ade80; border-radius: 10px; }

        .anchor-ui-box { 
            background: #1f2937; 
            border: 1px solid #374151; 
            padding: 12px; 
            border-radius: 8px; 
            margin-bottom: 10px;
        }
        .anchor-link { color: #4ade80 !important; text-decoration: none !important; font-weight: 700; }
        .anchor-link:hover { text-decoration: underline !important; color: #22c55e !important; }

        /* Metric Cards Alignment */
        .metric-card-inner { background-color: #1f2937; padding: 10px; border: 1px solid #374151; border-radius: 8px; text-align: center; margin-bottom: 8px; height: 95px; display: flex; flex-direction: column; justify-content: center; }
        .m-val { font-size: 1.0rem; font-weight: 900; color: #4ade80; }
        .m-lab { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; }

        /* Layout cleanup */
        .block-container { padding-top: 1.5rem !important; }
        label[data-testid="stWidgetLabel"] p { color: white !important; font-weight: 700 !important; }
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
        
        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    coords = geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0]
                    pts = np.array(coords)
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def render_map_go(df):
        map_df = df.copy()
        map_df['Color_Category'] = map_df['Eligibility_Status'].apply(lambda x: 1 if x == 'Eligible' else 0)
        active = st.session_state.get("active_tract")
        center = {"lat": 30.9, "lon": -91.8}
        zoom = 6.5

        if active and active in tract_centers:
            center = {"lat": tract_centers[active][1], "lon": tract_centers[active][0]}
            zoom = 12.0
        elif not map_df.empty:
            lats = [tract_centers[gid][1] for gid in map_df['geoid_str'] if gid in tract_centers]
            lons = [tract_centers[gid][0] for gid in map_df['geoid_str'] if gid in tract_centers]
            if lats and lons:
                center = {"lat": np.mean(lats), "lon": np.mean(lons)}
                lat_range, lon_range = max(lats)-min(lats), max(lons)-min(lons)
                max_range = max(lat_range, lon_range)
                zoom = 6.5 if max_range > 2 else 8.5 if max_range > 0.5 else 10.5

        fig = go.Figure(go.Choroplethmapbox(
            geojson=gj, locations=map_df['geoid_str'],
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#cbd5e1'], [1, '#4ade80']], 
            zmin=0, zmax=1, showscale=False,
            marker=dict(opacity=0.6, line=dict(width=0.5, color='white'))
        ))
        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)',
            height=500, clickmode='event+select', uirevision=str(zoom)+str(center)
        )
        return fig

    # --- SECTION 5: COMMAND CENTER ---
    st.markdown("### Strategic Analysis Command Center")
    
    # Global Filters
    f1, f2, f3 = st.columns([1, 1, 1])
    with f1: 
        selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]

    with f2: 
        selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]

    with f3: 
        search_q = st.text_input("Tract Search (GEOID)", placeholder="11-digit FIPS")
        if search_q and search_q in master_df['geoid_str'].values:
            st.session_state["active_tract"] = search_q

    st.plotly_chart(render_map_go(filtered_df), use_container_width=True, on_select="rerun", key="main_map")

    # --- SIDE-BY-SIDE ANALYSIS ROW ---
    st.markdown("<br>", unsafe_allow_html=True)
    curr_id = st.session_state["active_tract"]
    col_anchors, col_data, col_rec = st.columns([1, 1, 1]) # Perfectly even horizontal layout

    with col_anchors:
        st.markdown("#### 📍 Anchor Assets")
        anc_f = st.selectbox("Filter Assets", ["All Assets"] + sorted(anchors_df['Type'].unique().tolist()), label_visibility="collapsed")
        
        # This container matches the height of the Profile/Rec columns
        st.markdown("<div class='anchor-scroll-container'>", unsafe_allow_html=True)
        if curr_id and curr_id in tract_centers:
            lon, lat = tract_centers[curr_id]
            wa = anchors_df.copy()
            if anc_f != "All Assets": wa = wa[wa['Type'] == anc_f]
            wa['dist'] = wa.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            
            # Sort by distance and show top 30 for scrollability
            for _, a in wa.sort_values('dist').head(30).iterrows():
                # Link logic: uses the 'Link' column from your CSV
                asset_url = a.get('Link', '')
                if pd.notna(asset_url) and str(asset_url).strip() != "":
                    display_name = f"<a href='{asset_url}' target='_blank' class='anchor-link'>{a['Name']} ↗</a>"
                else:
                    display_name = f"<b>{a['Name']}</b>"

                st.markdown(f"""
                <div class='anchor-ui-box'>
                    <div style='color:#4ade80; font-size:0.7rem; font-weight:900;'>{a['Type'].upper()}</div>
                    {display_name}<br>
                    <small style='color:#94a3b8;'>{a['dist']:.1f} miles away</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Select a tract on the map.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col_data:
        st.markdown("#### 📊 Tract Profile")
        if curr_id:
            row = master_df[master_df["geoid_str"] == curr_id].iloc[0]
            if row['Eligibility_Status'] == 'Eligible':
                st.markdown("<div style='background-color:rgba(74, 222, 128, 0.1); border: 1px solid #4ade80; padding: 10px; border-radius: 8px; margin-bottom:12px; text-align:center;'><b style='color:#4ade80;'>✅ OZ 2.0 ELIGIBLE</b></div>", unsafe_allow_html=True)
            st.markdown(f"**GEOID:** `{curr_id}`")
            
            m_rows = [st.columns(3) for _ in range(3)]
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
            for i, (val, lab) in enumerate(metrics):
                m_rows[i//3][i%3].markdown(f"<div class='metric-card-inner'><div class='m-val'>{val}</div><div class='m-lab'>{lab}</div></div>", unsafe_allow_html=True)
        else:
            st.info("Select a tract to see metrics.")

    with col_rec:
        st.markdown("#### ✍️ Recommendation")
        cat = st.selectbox("Category", ["Industrial", "Housing", "Retail", "Infrastructure", "Other"])
        just = st.text_area("Justification", height=320, placeholder="Explain selection...")
        if st.button("Save to Report", use_container_width=True, type="primary"):
            if curr_id:
                st.session_state["session_recs"].append({"Tract": curr_id, "Category": cat, "Justification": just})
                st.toast("Saved!")

    # --- SECTION 6: FINAL REPORT ---
    st.markdown("---")
    st.markdown("### Final Report")
    if st.session_state["session_recs"]:
        st.dataframe(pd.DataFrame(st.session_state["session_recs"]), use_container_width=True, hide_index=True)
    else: st.info("No recommendations added yet.")