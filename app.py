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
    
    /* Metrics: White Titles, Soft Green Numbers */
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: 600; font-size: 0.75rem !important; }
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.3rem !important; }
    .stMetric { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 10px; }
    
    /* 2x2 Indicator Cards - All White Text */
    .indicator-box { border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 10px; border: 1px solid #334155; }
    .status-yes { background-color: rgba(74, 222, 128, 0.15); border-color: #4ade80; }
    .status-no { background-color: #1e293b; border-color: #334155; opacity: 0.6; }
    .indicator-label { font-size: 0.7rem; color: #ffffff; text-transform: uppercase; font-weight: 700; margin-bottom: 2px; }
    .indicator-value { font-size: 1rem; font-weight: 800; color: #ffffff; }
    
    /* Header Counter */
    .counter-pill { background: #4ade80; color: #0f172a; padding: 6px 15px; border-radius: 30px; font-weight: bold; font-size: 0.85rem; }
    
    /* Table Styling */
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 10px; }
    .anchor-table th { text-align: left; color: #94a3b8; border-bottom: 1px solid #334155; padding: 8px; }
    .anchor-table td { padding: 8px; border-bottom: 1px solid #1e293b; color: #cbd5e1; }
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Connection Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- 2. DATA UTILITIES ---
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
    df['map_status'] = np.where(df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 1, 0)

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

# --- 3. TOP BAR & COUNTER ---
try:
    hist = conn.read(worksheet="Sheet1", ttl=0)
    recs = len(hist[hist['User'] == st.session_state.get('username', '')])
except:
    recs = 0

t1, t2 = st.columns([0.7, 0.3])
with t1:
    st.title(f"Strategic Portal: {st.session_state.get('a_val', 'Louisiana')}")
with t2:
    st.markdown(f"<div style='text-align:right; margin-top:25px;'><span class='counter-pill'>RECOMMENDATIONS: {recs}</span></div>", unsafe_allow_html=True)

# --- 4. MAIN LAYOUT ---
col_map, col_side = st.columns([0.55, 0.45])

with col_side:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"<h3 style='color:#4ade80; margin-bottom:0;'>TRACT: {sid}</h3>", unsafe_allow_html=True)
        st.markdown(f"<p style='color:#94a3b8; margin-bottom:15px;'><b>PARISH:</b> {row.get('Parish')} | <b>REGION:</b> {row.get('Region', 'Louisiana')}</p>", unsafe_allow_html=True)
        
        def draw_ind(label, val):
            val_clean = str(val).lower()
            if "Metro (Urban)" in label: is_yes = 'metropolitan' in val_clean
            elif "Rural" in label: is_yes = 'rural' in val_clean
            else: is_yes = 'yes' in val_clean
            
            cls, txt = ("status-yes", "YES") if is_yes else ("status-no", "NO")
            return f"<div class='indicator-box {cls}'><div class='indicator-label'>{label}</div><div class='indicator-value'>{txt}</div></div>"

        # 2x2 Indicators
        i1, i2 = st.columns(2)
        mv = row.get('Metro Status (Metropolitan/Rural)', '')
        with i1:
            st.markdown(draw_ind("Metro (Urban)", mv), unsafe_allow_html=True)
            st.markdown(draw_ind("Rural", mv), unsafe_allow_html=True)
        with i2:
            st.markdown(draw_ind("NMTC Eligible", row.get('NMTC Eligible', '')), unsafe_allow_html=True)
            st.markdown(draw_ind("NMTC Deeply Distressed", row.get('NMTC Distressed', '')), unsafe_allow_html=True)

        # 8 Demographic Metrics
        m_map = {"home": "Median Home Value", "dis": "Disability Population (%)", "pop65": "Population 65 years and over", "labor": "Labor Force Participation (%)", "unemp": "Unemployment Rate (%)", "hs": "HS Degree or More (%)", "bach": "Bachelor's Degree or More (%)", "web": "Broadband Internet (%)"}
        for i in range(0, 8, 4):
            cols = st.columns(4)
            keys = list(m_map.keys())[i:i+4]
            for j, k in enumerate(keys):
                label = m_map[k].split('(')[0]
                cols[j].metric(label, safe_num(row.get(m_map[k]), "Home" in m_map[k]))

        # Nearest Anchors
        st.markdown("<p style='font-weight:bold; margin-top:20px; color:#ffffff;'>TOP 5 ASSET PROXIMITY</p>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_dist = anchor_df.copy()
            a_dist['d'] = a_dist.apply(lambda x: calculate_distance(t_pos['lat'], t_pos['lon'], x['lat'], x['lon']), axis=1)
            t5 = a_dist.sort_values('d').head(5)
            tbl = "<table class='anchor-table'><tr><th>DIST</th><th>NAME</th><th>TYPE</th></tr>"
            for _, a in t5.iterrows():
                tbl += f"<tr><td>{a['d']:.1f} mi</td><td>{a['name'].upper()}</td><td>{str(a.get('type','N/A')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)
    else:
        st.info("Select a tract on the map to view the strategic profile.")

with col_map:
    show_anchors = st.toggle("Show Anchors", value=False, help="Toggle off to make tract selection easier")
    
    fig = go.Figure()
    # TRACT POLYGONS
    fig.add_trace(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(74, 222, 128, 0.4)"]],
        showscale=False, marker_line_width=0.5, marker_line_color="#1e293b"
    ))
    
    # ANCHOR POINTS
    if show_anchors:
        fig.add_trace(go.Scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=6, color='#ffffff', opacity=0.7),
            text=anchor_df['name'], hoverinfo='text'
        ))

    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 31.0, "lon": -91.8}, zoom=6.0),
        height=750, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    
    ev = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if ev and ev.get("selection") and ev["selection"].get("points"):
        sel = ev["selection"]["points"][0]
        if "location" in sel:
            st.session_state["selected_tract"] = str(sel["location"]).zfill(11)

# --- 5. FORM ---
st.divider()
if not match.empty:
    st.subheader("STRATEGIC RECOMMENDATION")
    just = st.text_area("Justification:", height=100)
    if st.button("EXECUTE NOMINATION", type="primary"):
        st.success(f"Tract {sid} successfully nominated.")