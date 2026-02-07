import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM (OPTIMIZED FOR 100% VIEWPORT) ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    
    /* Text Blurbs */
    .intro-box { background: white; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; margin-bottom: 8px; }
    .best-practice { background: #fefce8; padding: 8px; border-left: 4px solid #facc15; font-size: 0.8rem; margin-bottom: 8px; color: #854d0e; }
    
    /* Progress & Header */
    .stat-pill { background: #1e293b; color: #4ade80; padding: 2px 10px; border-radius: 12px; font-weight: 800; font-size: 0.75rem; }
    .profile-header { background-color: #1e293b; padding: 10px; border-radius: 8px; border-left: 6px solid #22c55e; margin-bottom: 10px; color: white; }
    .header-item { display: inline-block; margin-right: 15px; }
    .header-label { color: #94a3b8; font-size: 0.65rem; text-transform: uppercase; display: block; }
    .header-value { color: #ffffff; font-size: 0.9rem; font-weight: 700; }

    /* Shrunk Metrics - White text on dark blue background */
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.1rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #cbd5e1 !important; font-size: 0.7rem !important; text-transform: uppercase; }
    [data-testid="stMetric"] { background-color: #334155; border-radius: 6px; padding: 8px !important; border: 1px solid #475569; }
    
    /* Indicators */
    .indicator-box { border-radius: 6px; padding: 5px; text-align: center; margin-bottom: 5px; border: 1px solid #e2e8f0; height: 55px; display: flex; flex-direction: column; justify-content: center; background: white; }
    .status-yes { background-color: #dcfce7; border-color: #22c55e !important; color: #166534; }
    .status-no { background-color: #f1f5f9; border-color: #cbd5e1 !important; opacity: 0.6; color: #64748b; }
    .indicator-label { font-size: 0.6rem; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 0.8rem; font-weight: 900; }
    
    .section-label { color: #475569; font-size: 0.7rem; font-weight: 800; margin-top: 8px; border-bottom: 1px solid #e2e8f0; padding-bottom: 2px; text-transform: uppercase; }
    .stProgress > div > div > div > div { background-color: #22c55e; height: 6px; }
    
    /* Anchors Table */
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.7rem; background: white; }
    .anchor-table td { padding: 4px; border-bottom: 1px solid #f1f5f9; }
    .anchor-table th { text-align: left; color: #64748b; font-size: 0.6rem; padding: 4px; background: #f8fafc; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA LOAD (RESILIENT ERROR HANDLING) ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    BASE_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
    def find_col(keywords):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keywords): return col
        return None

    cols = {
        "unemp": find_col(['unemployment', 'rate']),
        "metro": find_col(['metro', 'status']),
        "hs": find_col(['hs', 'degree']) or find_col(['high', 'school']),
        "bach": find_col(['bachelor']),
        "labor": find_col(['labor', 'force']),
        "home": find_col(['median', 'home', 'value']),
        "pov": POV_COL, "base": BASE_COL
    }

    # GEOID Preparation
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # Logic Calculations
    df['pov_val'] = df[POV_COL].apply(clean) if POV_COL in df.columns else 0.0
    df['unemp_val'] = df[cols['unemp']].apply(clean) if cols['unemp'] else 0.0
    df['is_nmtc'] = df['pov_val'] >= 20.0
    df['is_deeply'] = (df['pov_val'] > 40.0) | (df['unemp_val'] >= 10.5)

    # RESILIENT ELIGIBILITY CHECK
    elig_col = find_col(['5-year', 'eligibility']) or find_col(['OZ', 'Eligible'])
    if elig_col:
        df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y'])
    else:
        # Fallback to Poverty Rule if specific column is missing
        df['is_eligible'] = df['is_nmtc']
    
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

    # Assets & GeoJSON
    try:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    except:
        a = pd.read_csv("la_anchors.csv")
    a.columns = a.columns.str.strip().str.lower()
    
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        gid = str(feat['properties'].get('GEOID', '')).zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        if 'INTPTLAT' in feat['properties']:
            centers[gid] = {"lat": float(str(feat['properties']['INTPTLAT']).replace('+','')), "lon": float(str(feat['properties']['INTPTLON']).replace('+',''))}

    return df, gj, a, centers, cols

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

# --- 3. SESSION STATE ---
if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

# --- 4. TOP LEVEL CONTENT ---
st.markdown("""
<div class='intro-box'>
    <h5 style='margin:0; color:#1e293b; font-size:1rem;'>Strategic Portal: Louisiana OZ 2.0</h5>
    <p style='font-size:0.75rem; margin:3px 0;'>Welcome to the <b>American Dynamism Strategic Portal</b>. Use this interface to identify high-potential census tracts for the 2026 investment portfolio.</p>
    <p style='font-size:0.75rem; margin:0;'><b>Directions:</b> Eligible tracts are <b>Green</b>. Click any green tract to view demographics and nearest anchors. Click 'Nominate' to add to your target list.</p>
</div>
""", unsafe_allow_html=True)

# --- 5. MAIN DASHBOARD ---
col_map, col_side = st.columns([0.5, 0.5])

with col_map:
    # High-contrast mapping for context and selection
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(200,200,200,0.15)"], [1, "rgba(34, 197, 94, 0.85)"]],
        showscale=False, marker_line_width=0.3, marker_line_color="#475569"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 30.8, "lon": -91.8}, zoom=6.0),
        height=620, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="v67_map")
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        st.rerun()

with col_side:
    st.markdown("<div class='best-practice'><b>Best Practice:</b> Prioritize tracts within 10 miles of deep-water ports or research universities.</div>", unsafe_allow_html=True)
    
    st.markdown(f"<div style='display:flex; justify-content:space-between; align-items:center; font-size:0.8rem;'><b>PROGRESS</b> <span class='stat-pill'>{st.session_state.recom_count} / 150</span></div>", unsafe_allow_html=True)
    st.progress(min(st.session_state.recom_count / 150, 1.0))

    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"""
            <div class='profile-header'>
                <div class='header-item'><span class='header-label'>Tract ID</span><span class='header-value'>{sid}</span></div>
                <div class='header-item'><span class='header-label'>Parish</span><span class='header-value'>{row.get('Parish')}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # QUALIFICATION ROW
        m1, m2, m3, m4 = st.columns(4)
        m_val = str(row.get(cols['metro'], '')).lower()
        with m1: st.markdown(f"<div class='indicator-box {'status-yes' if 'metro' in m_val else 'status-no'}'><div class='indicator-label'>Urban</div><div class='indicator-value'>{'YES' if 'metro' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='indicator-box {'status-yes' if 'rural' in m_val else 'status-no'}'><div class='indicator-label'>Rural</div><div class='indicator-value'>{'YES' if 'rural' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc'] else 'status-no'}'><div class='indicator-label'>NMTC</div><div class='indicator-value'>{'YES' if row['is_nmtc'] else 'NO'}</div></div>", unsafe_allow_html=True)
        with m4: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_deeply'] else 'status-no'}'><div class='indicator-label'>Deep Dist.</div><div class='indicator-value'>{'YES' if row['is_deeply'] else 'NO'}</div></div>", unsafe_allow_html=True)

        # 8 METRIC CARDS (SHRUNK)
        def f_val(c, is_p=True, is_d=False):
            v = row.get(c, 0)
            try:
                num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
                return f"${num:,.0f}" if is_d else (f"{num:,.1f}%" if is_p else f"{num:,.0f}")
            except: return "N/A"

        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Poverty", f_val(cols['pov'])); r2.metric("Unempl.", f_val(cols['unemp'])); r3.metric("Labor", f_val(cols['labor'])); r4.metric("Home Val", f_val(cols['home'], False, True))
        
        r5, r6, r7, r8 = st.columns(4)
        r5.metric("HS Grad", f_val(cols['hs'])); r6.metric("Bach.", f_val(cols['bach']))
        try:
            bp = float(str(row.get(cols['base'])).replace(',',''))
            r65 = float(str(row.get("Population 65 years and over")).replace(',',''))
            r7.metric("Base Pop", f"{bp:,.0f}"); r8.metric("65+ %", f"{(r65/bp)*100:,.1f}%")
        except:
            r7.metric("Base Pop", "N/A"); r8.metric("65+ %", "N/A")

        # ANCHORS
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_df = anchor_df.copy()
            a_df['dist'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
            t7 = a_df.sort_values('dist').head(6) 
            tbl = "<table class='anchor-table'><tr><th>DIST</th><th>ASSET</th><th>TYPE</th></tr>"
            for _, a in t7.iterrows():
                tbl += f"<tr><td><b>{a['dist']:.1f}mi</b></td><td>{a['name'].upper()}</td><td>{str(a.get('type','')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)

        if st.button("NOMINATE TRACT", type="primary", use_container_width=True):
            st.session_state.recom_count += 1
            st.success(f"Nominated {sid}"); st.rerun()
    else:
        st.info("Select a green tract on the map to analyze.")