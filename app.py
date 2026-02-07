import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    
    /* Profile Header Styling */
    .profile-header { background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #4ade80; margin-bottom: 20px; }
    .header-item { display: inline-block; margin-right: 30px; }
    .header-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; font-weight: 700; display: block; }
    .header-value { color: #ffffff; font-size: 1.2rem; font-weight: 800; }

    /* Progress Bar Customization */
    .stProgress > div > div > div > div { background-color: #4ade80; }
    
    /* Metric & Indicator Boxes */
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: 700; font-size: 0.95rem !important; }
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.7rem !important; font-weight: 800; }
    .stMetric { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 15px; }
    
    .indicator-box { border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 12px; border: 1px solid #475569; }
    .status-yes { background-color: rgba(74, 222, 128, 0.25); border-color: #4ade80; }
    .status-no { background-color: #1e293b; border-color: #334155; opacity: 0.5; }
    .indicator-label { font-size: 0.85rem; color: #ffffff; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 1.2rem; font-weight: 900; color: #ffffff; }
    
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    .anchor-table th { text-align: left; color: #cbd5e1; border-bottom: 2px solid #4ade80; padding: 10px; }
    .anchor-table td { padding: 10px; border-bottom: 1px solid #334155; color: #f1f5f9; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    try:
        a = pd.read_csv("la_anchors.csv")
    except:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    df['is_eligible'] = df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y'])
    df['map_status'] = np.where(df['is_eligible'], 1, 0)

    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        lat, lon = p.get('INTPTLAT'), p.get('INTPTLON')
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}
    return df, gj, a, centers

master_df, la_geojson, anchor_df, tract_centers = load_data()

# --- 3. STATE ---
if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

# --- 4. TOP BAR ---
t1, t2 = st.columns([0.7, 0.3])
with t1:
    st.title("Strategic Portal: Louisiana")
with t2:
    st.markdown(f"<div style='text-align:right; margin-top:20px;'><span class='counter-pill'>TOTAL NOMINATIONS: {st.session_state.recom_count}</span></div>", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    fig = go.Figure()
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(200,200,200,0.1)"], [1, "rgba(74, 222, 128, 0.65)"]],
        showscale=False, marker_line_width=1, marker_line_color="#1e293b"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 31.0, "lon": -91.8}, zoom=6.2),
        height=950, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="oz_map_v51")
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        new_sid = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        if st.session_state.selected_tract != new_sid:
            st.session_state.selected_tract = new_sid
            st.rerun()

with col_side:
    # 5a. Progress Bar
    st.markdown("<p style='font-weight:700; margin-bottom:5px;'>NOMINATION TARGET PROGRESS (Goal: 150)</p>", unsafe_allow_html=True)
    progress_val = min(st.session_state.recom_count / 150, 1.0)
    st.progress(progress_val)
    
    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        # 5b. Horizontal Header
        st.markdown(f"""
            <div class='profile-header'>
                <div class='header-item'><span class='header-label'>Tract ID</span><span class='header-value'>{sid}</span></div>
                <div class='header-item'><span class='header-label'>Parish</span><span class='header-value'>{row.get('Parish')}</span></div>
                <div class='header-item'><span class='header-label'>Region</span><span class='header-value'>{row.get('Region', 'Louisiana')}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # 5c. Indicators
        i1, i2 = st.columns(2)
        mv = str(row.get('Metro Status (Metropolitan/Rural)', '')).lower()
        with i1:
            st.markdown(f"<div class='indicator-box {'status-yes' if 'metropolitan' in mv else 'status-no'}'><div class='indicator-label'>Metro (Urban)</div><div class='indicator-value'>{'YES' if 'metropolitan' in mv else 'NO'}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='indicator-box {'status-yes' if 'rural' in mv else 'status-no'}'><div class='indicator-label'>Rural</div><div class='indicator-value'>{'YES' if 'rural' in mv else 'NO'}</div></div>", unsafe_allow_html=True)
        with i2:
            st.markdown(f"<div class='indicator-box {'status-yes' if 'yes' in str(row.get('NMTC Eligible','')).lower() else 'status-no'}'><div class='indicator-label'>NMTC Eligible</div><div class='indicator-value'>{'YES' if 'yes' in str(row.get('NMTC Eligible','')).lower() else 'NO'}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='indicator-box {'status-yes' if 'yes' in str(row.get('NMTC Distressed','')).lower() else 'status-no'}'><div class='indicator-label'>NMTC Deeply Distressed</div><div class='indicator-value'>{'YES' if 'yes' in str(row.get('NMTC Distressed','')).lower() else 'NO'}</div></div>", unsafe_allow_html=True)

        # 5d. Demographic Metrics
        m_map = {"Median Home Value": "home", "Disability Population (%)": "dis", "Population 65 years and over": "pop65", "Labor Force Participation (%)": "labor", "Unemployment Rate (%)": "unemp", "HS Degree or More (%)": "hs", "Bachelor's Degree or More (%)": "bach", "Broadband Internet (%)": "web"}
        metrics_list = list(m_map.keys())
        for i in range(0, 8, 4):
            cols = st.columns(4)
            for j, m_name in enumerate(metrics_list[i:i+4]):
                val = row.get(m_name, "N/A")
                try:
                    f_val = f"${float(str(val).replace('$','').replace(',','')):,.0f}" if "Home" in m_name else f"{float(val):,.1f}%"
                except: f_val = "N/A"
                cols[j].metric(m_name.split('(')[0], f_val)

        # 5e. Assets
        st.markdown("<p style='font-weight:800; margin-top:20px; color:#ffffff;'>TOP 5 ASSET PROXIMITY</p>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_df = anchor_df.copy()
            a_df['d'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
            t5 = a_df.sort_values('d').head(5)
            tbl = "<table class='anchor-table'><tr><th>DIST</th><th>NAME</th><th>TYPE</th></tr>"
            for _, a in t5.iterrows():
                tbl += f"<tr><td>{a['d']:.1f}m</td><td>{a['name'][:30].upper()}</td><td>{str(a.get('type','')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)

        # 5f. Nomination
        st.divider()
        st.subheader("STRATEGIC NOMINATION")
        cat = st.selectbox("Category", ["Energy Transition", "Cybersecurity", "Critical Mfg", "Defense Tech"])
        just = st.text_area("Justification (Required)")
        if st.button("EXECUTE NOMINATION", type="primary"):
            if just:
                st.session_state.recom_count += 1
                st.success(f"Tract {sid} nominated.")
                st.rerun()
            else: st.warning("Please provide justification.")
    else:
        st.info("Select a green-highlighted tract on the map to begin.")

# --- 6. DIRECTORY ---
st.divider()
st.subheader("📍 ELIGIBLE TRACTS DIRECTORY")
st.dataframe(master_df[master_df['is_eligible'] == True][['GEOID_KEY', 'Parish', 'Region', 'Metro Status (Metropolitan/Rural)']], use_container_width=True, hide_index=True)