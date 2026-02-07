import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. DESIGN SYSTEM (LIGHT MAP & LARGE TEXT) ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    
    /* Large Metrics */
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: 700; font-size: 1rem !important; }
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.8rem !important; font-weight: 800; }
    .stMetric { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 15px; }
    
    /* High-Visibility 2x2 Indicators */
    .indicator-box { border-radius: 8px; padding: 18px; text-align: center; margin-bottom: 15px; border: 1px solid #475569; }
    .status-yes { background-color: rgba(74, 222, 128, 0.25); border-color: #4ade80; }
    .status-no { background-color: #1e293b; border-color: #334155; opacity: 0.5; }
    .indicator-label { font-size: 0.95rem; color: #ffffff; text-transform: uppercase; font-weight: 800; margin-bottom: 5px; }
    .indicator-value { font-size: 1.4rem; font-weight: 900; color: #ffffff; }
    
    /* Typography */
    .stMarkdown p, .stMarkdown li { font-size: 1.1rem !important; line-height: 1.6; }
    h3 { font-size: 1.8rem !important; font-weight: 800 !important; }
    
    .counter-pill { background: #4ade80; color: #0f172a; padding: 10px 25px; border-radius: 30px; font-weight: 900; font-size: 1.1rem; }
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 1rem; margin-top: 15px; }
    .anchor-table th { text-align: left; color: #cbd5e1; border-bottom: 2px solid #4ade80; padding: 12px; }
    .anchor-table td { padding: 12px; border-bottom: 1px solid #334155; color: #f1f5f9; }
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

def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        p1, p2 = np.radians(float(lat1)), np.radians(float(lat2))
        dp, dl = np.radians(float(lat2)-float(lat1)), np.radians(float(lon2)-float(lon1))
        a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.0

def safe_num(val, is_money=False):
    try:
        if pd.isna(val) or str(val).strip().lower() in ['n/a', 'nan', '']: return "N/A"
        n = float(str(val).replace('$', '').replace(',', '').replace('%', '').strip())
        return f"${n:,.0f}" if is_money else (f"{n:,.1f}%" if n <= 100 and n > 0 else f"{n:,.0f}")
    except: return "N/A"

master_df, la_geojson, anchor_df, tract_centers = load_data()

# --- 3. PERSISTENT COUNTER ---
if "recom_count" not in st.session_state:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        hist = conn.read(worksheet="Sheet1", ttl=0)
        st.session_state.recom_count = len(hist)
    except:
        st.session_state.recom_count = 0

# --- 4. TOP BAR ---
t1, t2 = st.columns([0.7, 0.3])
with t1:
    st.title(f"Strategic Portal: {st.session_state.get('a_val', 'Louisiana')}")
with t2:
    st.markdown(f"<div style='text-align:right; margin-top:20px;'><span class='counter-pill'>RECOMMENDATIONS: {st.session_state.recom_count}</span></div>", unsafe_allow_html=True)

# --- 5. MAIN LAYOUT ---
col_map, col_side = st.columns([0.55, 0.45])

with col_side:
    sid = st.session_state.get("selected_tract")
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"<h3 style='color:#4ade80; margin-bottom:5px;'>TRACT: {sid}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#94a3b8; font-size:1.2rem !important; font-weight:600;'>PARISH: {row.get('Parish')} | REGION: {row.get('Region', 'Louisiana')}</p>", unsafe_allow_html=True)
        
        def draw_ind(label, val):
            v_clean = str(val).lower()
            if "Metro" in label: is_yes = 'metropolitan' in v_clean
            elif "Rural" in label: is_yes = 'rural' in v_clean
            else: is_yes = 'yes' in v_clean
            cls, txt = ("status-yes", "YES") if is_yes else ("status-no", "NO")
            return f"<div class='indicator-box {cls}'><div class='indicator-label'>{label}</div><div class='indicator-value'>{txt}</div></div>"

        i1, i2 = st.columns(2)
        mv = row.get('Metro Status (Metropolitan/Rural)', '')
        with i1:
            st.markdown(draw_ind("Metro (Urban)", mv), unsafe_allow_html=True)
            st.markdown(draw_ind("Rural", mv), unsafe_allow_html=True)
        with i2:
            st.markdown(draw_ind("NMTC Eligible", row.get('NMTC Eligible', '')), unsafe_allow_html=True)
            st.markdown(draw_ind("NMTC Deeply Distressed", row.get('NMTC Distressed', '')), unsafe_allow_html=True)

        # Large Metrics
        m_map = {"home": "Median Home Value", "dis": "Disability Population (%)", "pop65": "Population 65 years and over", "labor": "Labor Force Participation (%)", "unemp": "Unemployment Rate (%)", "hs": "HS Degree or More (%)", "bach": "Bachelor's Degree or More (%)", "web": "Broadband Internet (%)"}
        for i in range(0, 8, 4):
            cols = st.columns(4)
            keys = list(m_map.keys())[i:i+4]
            for j, k in enumerate(keys):
                cols[j].metric(m_map[k].split('(')[0], safe_num(row.get(m_map[k]), "Home" in m_map[k]))

        # Anchors
        st.markdown("<p style='font-weight:800; margin-top:25px; color:#ffffff; font-size:1.2rem;'>TOP 5 ASSET PROXIMITY</p>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_dist = anchor_df.copy()
            a_dist['d'] = a_dist.apply(lambda x: calculate_distance(t_pos['lat'], t_pos['lon'], x['lat'], x['lon']), axis=1)
            t5 = a_dist.sort_values('d').head(5)
            tbl = "<table class='anchor-table'><tr><th>DISTANCE</th><th>NAME</th><th>TYPE</th></tr>"
            for _, a in t5.iterrows():
                tbl += f"<tr><td><b>{a['d']:.1f} mi</b></td><td>{a['name'].upper()}</td><td>{str(a.get('type','N/A')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)
    else:
        st.info("Select a tract on the map to begin strategic analysis.")

with col_map:
    show_anchors = st.toggle("Overlay Assets", value=False)
    
    fig = go.Figure()
    # TRACTS
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(200,200,200,0.1)"], [1, "rgba(74, 222, 128, 0.6)"]],
        showscale=False, marker_line_width=1, marker_line_color="#ffffff"
    ))
    # ANCHORS
    if show_anchors:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=8, color='#0f172a', opacity=0.9),
            text=anchor_df['name'], hoverinfo='text'
        ))

    fig.update_layout(
        # LIGHT BACKGROUND STYLE
        mapbox=dict(
            style="light", 
            center={"lat": 31.0, "lon": -91.8}, 
            zoom=6.0,
            layers=[{
                "below": 'traces',
                "type": "background",
                "color": "#f8fafc"
            }]
        ),
        height=750, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    
    # White Labeling via Font Color in Layout
    fig.update_layout(font=dict(color="#ffffff"))

    ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if ev and ev.get("selection") and ev["selection"].get("points"):
        sel = ev["selection"]["points"][0]
        if "location" in sel:
            st.session_state["selected_tract"] = str(sel["location"]).zfill(11)

# --- 6. ELIGIBLE TRACTS LIST ---
st.divider()
st.subheader("📍 ELIGIBLE TRACTS EXPLORER")
eligible_list = master_df[master_df['is_eligible'] == True][['GEOID_KEY', 'Parish', 'Region', 'Metro Status (Metropolitan/Rural)']]
st.dataframe(eligible_list, use_container_width=True, hide_index=True)

# --- 7. FORM ---
if not match.empty:
    st.divider()
    st.subheader("STRATEGIC RECOMMENDATION")
    just = st.text_area("Justification:", height=100)
    if st.button("EXECUTE NOMINATION", type="primary"):
        st.session_state.recom_count += 1
        st.success(f"Tract {sid} nominated. Recommendation counter updated.")
        st.rerun()