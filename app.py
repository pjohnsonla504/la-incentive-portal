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
    
    .profile-header { background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #4ade80; margin-bottom: 20px; }
    .header-item { display: inline-block; margin-right: 30px; }
    .header-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; font-weight: 700; display: block; }
    .header-value { color: #ffffff; font-size: 1.2rem; font-weight: 800; }

    .stProgress > div > div > div > div { background-color: #4ade80; }
    
    [data-testid="stMetricLabel"] { color: #ffffff !important; font-weight: 700; font-size: 0.85rem !important; }
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.5rem !important; font-weight: 800; }
    .stMetric { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 12px; }
    
    /* Functional Indicator Logic */
    .indicator-box { border-radius: 8px; padding: 15px; text-align: center; margin-bottom: 12px; border: 2px solid #475569; transition: 0.3s; }
    .status-yes { background-color: rgba(74, 222, 128, 0.2); border-color: #4ade80 !important; box-shadow: 0 0 10px rgba(74, 222, 128, 0.1); }
    .status-no { background-color: rgba(30, 41, 59, 0.5); border-color: #334155 !important; opacity: 0.6; }
    .indicator-label { font-size: 0.75rem; color: #ffffff; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 1.1rem; font-weight: 900; color: #ffffff; }
    
    .section-label { color: #94a3b8; font-size: 0.85rem; font-weight: 800; margin-top: 15px; margin-bottom: 10px; text-transform: uppercase; border-bottom: 1px solid #334155; padding-bottom: 5px; }
    
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
    
    # Track Highlighted Green 
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
        height=1020, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="oz_map_v55")
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        new_sid = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        if st.session_state.selected_tract != new_sid:
            st.session_state.selected_tract = new_sid
            st.rerun()

with col_side:
    st.markdown("<p style='font-weight:700; margin-bottom:5px;'>NOMINATION TARGET PROGRESS (Goal: 150)</p>", unsafe_allow_html=True)
    st.progress(min(st.session_state.recom_count / 150, 1.0))
    
    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        # Profile Header
        st.markdown(f"""
            <div class='profile-header'>
                <div class='header-item'><span class='header-label'>Tract ID</span><span class='header-value'>{sid}</span></div>
                <div class='header-item'><span class='header-label'>Parish</span><span class='header-value'>{row.get('Parish')}</span></div>
                <div class='header-item'><span class='header-label'>Region</span><span class='header-value'>{row.get('Region', 'Louisiana')}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # Qualification Indicators Logic
        st.markdown("<div class='section-label'>Qualification Indicators</div>", unsafe_allow_html=True)
        i1, i2 = st.columns(2)
        
        # 1. Metro/Rural Logic
        mv = str(row.get('Metro Status (Metropolitan/Rural)', '')).lower()
        is_metro = 'metropolitan' in mv
        is_rural = 'rural' in mv
        
        # 2. NMTC Logic
        nmtc_val = str(row.get('NMTC Eligible', '')).lower().strip()
        nmtc_dist = str(row.get('NMTC Distressed', '')).lower().strip()
        is_nmtc = nmtc_val in ['yes', 'eligible', 'y']
        is_distressed = nmtc_dist in ['yes', 'distressed', 'y', 'deeply distressed']

        with i1:
            st.markdown(f"<div class='indicator-box {'status-yes' if is_metro else 'status-no'}'><div class='indicator-label'>Metro (Urban)</div><div class='indicator-value'>{'YES' if is_metro else 'NO'}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='indicator-box {'status-yes' if is_rural else 'status-no'}'><div class='indicator-label'>Rural Area</div><div class='indicator-value'>{'YES' if is_rural else 'NO'}</div></div>", unsafe_allow_html=True)
        with i2:
            st.markdown(f"<div class='indicator-box {'status-yes' if is_nmtc else 'status-no'}'><div class='indicator-label'>NMTC Eligible</div><div class='indicator-value'>{'YES' if is_nmtc else 'NO'}</div></div>", unsafe_allow_html=True)
            st.markdown(f"<div class='indicator-box {'status-yes' if is_distressed else 'status-no'}'><div class='indicator-label'>NMTC Deeply Distressed</div><div class='indicator-value'>{'YES' if is_distressed else 'NO'}</div></div>", unsafe_allow_html=True)

        # Economic Health
        st.markdown("<div class='section-label'>Economic Health</div>", unsafe_allow_html=True)
        e1, e2, e3, e4 = st.columns(4)
        def fmt(v, is_m=False):
            try: 
                clean = str(v).replace('$','').replace(',','').replace('%','').strip()
                return f"${float(clean):,.0f}" if is_m else f"{float(clean):,.1f}%"
            except: return "N/A"
        
        e1.metric("Median Home Value", fmt(row.get("Median Home Value"), True))
        e2.metric("Labor Participation", fmt(row.get("Labor Force Participation (%)")))
        e3.metric("Unemployment", fmt(row.get("Unemployment Rate (%)")))
        e4.metric("Broadband Access", fmt(row.get("Broadband Internet (%)")))

        # Human Capital
        st.markdown("<div class='section-label'>Human Capital & Demographics</div>", unsafe_allow_html=True)
        h1, h2, h3, h4 = st.columns(4)
        try:
            base_pop = float(str(row.get("Estimate!!Total!!Population for whom poverty status is determined")).replace(",",""))
            raw_65 = float(str(row.get("Population 65 years and over")).replace(",",""))
            calc_pct_65 = (raw_65 / base_pop) * 100 if base_pop > 0 else 0
            pop_display = f"{base_pop:,.0f}"
            elderly_display = f"{calc_pct_65:,.1f}%"
        except:
            pop_display = "N/A"
            elderly_display = "N/A"

        h1.metric("Base Population", pop_display)
        h2.metric("Elderly (65+ %)", elderly_display)
        h3.metric("HS Grad+", fmt(row.get("HS Degree or More (%)")))
        h4.metric("Bachelor's+", fmt(row.get("Bachelor's Degree or More (%)")))

        # Asset Proximity
        st.markdown("<div class='section-label'>Asset Proximity</div>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_df = anchor_df.copy()
            a_df['d'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
            t5 = a_df.sort_values('d').head(5)
            tbl = "<table class='anchor-table'><tr><th>DIST</th><th>NAME</th><th>TYPE</th></tr>"
            for _, a in t5.iterrows():
                tbl += f"<tr><td>{a['d']:.1f}m</td><td>{a['name'][:30].upper()}</td><td>{str(a.get('type','')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)

        # Nomination Form
        st.divider()
        st.subheader("STRATEGIC NOMINATION")
        cat = st.selectbox("Investment Category", ["Energy Transition", "Cybersecurity", "Critical Mfg", "Defense Tech"])
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