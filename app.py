import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    
    /* Progress & Stats */
    .stat-pill { background: #1e293b; color: #4ade80; padding: 5px 15px; border-radius: 20px; font-weight: 800; font-size: 0.9rem; border: 1px solid #475569; }
    
    /* Profile Header */
    .profile-header { background-color: #1e293b; padding: 20px; border-radius: 12px; border-left: 8px solid #22c55e; margin-bottom: 25px; color: white; }
    .header-item { display: inline-block; margin-right: 40px; }
    .header-label { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; font-weight: 700; display: block; }
    .header-value { color: #ffffff; font-size: 1.3rem; font-weight: 800; }

    /* Large White-Text Metric Cards */
    [data-testid="stMetricValue"] { color: #ffffff !important; font-size: 1.8rem !important; font-weight: 800 !important; }
    [data-testid="stMetricLabel"] { color: #cbd5e1 !important; font-weight: 700 !important; font-size: 0.9rem !important; text-transform: uppercase; }
    [data-testid="stMetric"] { background-color: #334155; border-radius: 12px; padding: 20px !important; border: 1px solid #475569; }
    
    /* Indicators */
    .indicator-box { border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 12px; border: 2px solid #e2e8f0; height: 100px; display: flex; flex-direction: column; justify-content: center; background: white; }
    .status-yes { background-color: #dcfce7; border-color: #22c55e !important; color: #166534; }
    .status-no { background-color: #f1f5f9; border-color: #cbd5e1 !important; opacity: 0.7; color: #64748b; }
    .indicator-label { font-size: 0.75rem; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 1.2rem; font-weight: 900; margin-top: 5px; }
    
    .section-label { color: #475569; font-size: 1rem; font-weight: 800; margin-top: 25px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; text-transform: uppercase; }
    .stProgress > div > div > div > div { background-color: #22c55e; }
    
    /* Anchors Table */
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.9rem; background: white; margin-top: 10px; }
    .anchor-table td { padding: 10px; border-bottom: 1px solid #f1f5f9; color: #1e293b; }
    .anchor-table th { text-align: left; color: #64748b; font-size: 0.75rem; padding: 10px; background: #f8fafc; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA LOAD ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Critical Mappings
    POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    BASE_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
    def find_col(keywords):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keywords): return col
        return None

    unemp_col = find_col(['unemployment', 'rate'])
    metro_col = find_col(['metro', 'status'])
    edu_hs = find_col(['hs', 'degree']) or find_col(['high', 'school'])
    edu_bach = find_col(['bachelor'])
    labor_col = find_col(['labor', 'force'])
    home_val = find_col(['median', 'home', 'value'])

    # GEOID Standardization
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # NMTC & DISTRESS CALCULATIONS
    df['pov_val'] = df[POV_COL].apply(clean) if POV_COL in df.columns else 0.0
    df['unemp_val'] = df[unemp_col].apply(clean) if unemp_col else 0.0
    
    df['is_nmtc'] = df['pov_val'] >= 20.0
    df['is_deeply'] = (df['pov_val'] > 40.0) | (df['unemp_val'] >= 10.5)

    # MAP FILTER: ONLY ELIGIBLE TRACTS GREEN
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else False
    # Set non-eligible to NaN so they don't get colored
    df['map_color'] = np.where(df['is_eligible'], 1, np.nan)

    # Load Assets & GeoJSON
    try: a = pd.read_csv("la_anchors.csv")
    except: a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        if 'INTPTLAT' in p:
            centers[gid] = {"lat": float(str(p['INTPTLAT']).replace('+','')), "lon": float(str(p['INTPTLON']).replace('+',''))}

    return df, gj, a, centers, {
        "pov": POV_COL, "base": BASE_COL, "unemp": unemp_col, "metro": metro_col, 
        "hs": edu_hs, "bach": edu_bach, "labor": labor_col, "home": home_val
    }

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

# --- 3. SESSION STATE ---
if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

# --- 4. TOP BAR ---
t1, t2 = st.columns([0.7, 0.3])
with t1:
    st.title("Strategic Portal: Louisiana OZ 2.0")
with t2:
    st.markdown(f"<div style='text-align:right; margin-top:20px;'><span class='stat-pill'>NOMINATIONS: {st.session_state.recom_count} / 150</span></div>", unsafe_allow_html=True)

# --- 5. MAIN INTERFACE ---
col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    # Lighter map, strict green for eligible
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_color'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(34, 197, 94, 0.75)"], [1, "rgba(34, 197, 94, 0.75)"]],
        showscale=False, marker_line_width=0.5, marker_line_color="#1e293b",
        nan_color="rgba(0,0,0,0)" # Non-eligible are transparent
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 31.0, "lon": -91.8}, zoom=6.5),
        height=1020, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="v64_map")
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        st.rerun()

with col_side:
    st.markdown("<p style='font-weight:700; margin-bottom:5px;'>PORTFOLIO TARGET PROGRESS</p>", unsafe_allow_html=True)
    st.progress(min(st.session_state.recom_count / 150, 1.0))

    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"""
            <div class='profile-header'>
                <div class='header-item'><span class='header-label'>Tract ID</span><span class='header-value'>{sid}</span></div>
                <div class='header-item'><span class='header-label'>Parish</span><span class='header-value'>{row.get('Parish')}</span></div>
                <div class='header-item'><span class='header-label'>Region</span><span class='header-value'>{row.get('Region', 'Louisiana')}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # INDICATORS
        st.markdown("<div class='section-label'>Qualification Indicators</div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m_val = str(row.get(cols['metro'], '')).lower()
        with m1: st.markdown(f"<div class='indicator-box {'status-yes' if 'metro' in m_val else 'status-no'}'><div class='indicator-label'>Urban</div><div class='indicator-value'>{'YES' if 'metro' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='indicator-box {'status-yes' if 'rural' in m_val else 'status-no'}'><div class='indicator-label'>Rural</div><div class='indicator-value'>{'YES' if 'rural' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc'] else 'status-no'}'><div class='indicator-label'>NMTC</div><div class='indicator-value'>{'YES' if row['is_nmtc'] else 'NO'}</div></div>", unsafe_allow_html=True)
        with m4: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_deeply'] else 'status-no'}'><div class='indicator-label'>Deeply Dist.</div><div class='indicator-value'>{'YES' if row['is_deeply'] else 'NO'}</div></div>", unsafe_allow_html=True)

        # 8 METRIC CARDS (LARGE / WHITE TEXT)
        st.markdown("<div class='section-label'>Economic & Demographic Profile</div>", unsafe_allow_html=True)
        
        def f_val(c, is_p=True, is_d=False):
            v = row.get(c, 0)
            try:
                num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
                if is_d: return f"${num:,.0f}"
                return f"{num:,.1f}%" if is_p else f"{num:,.0f}"
            except: return "N/A"

        c1, c2 = st.columns(2)
        c1.metric("Poverty Rate", f_val(cols['pov']))
        c2.metric("Unemployment", f_val(cols['unemp']))
        
        c3, c4 = st.columns(2)
        c3.metric("Labor Participation", f_val(cols['labor']))
        c4.metric("Median Home Value", f_val(cols['home'], False, True))
        
        c5, c6 = st.columns(2)
        c5.metric("High School Grad+", f_val(cols['hs']))
        c6.metric("Bachelor's Degree+", f_val(cols['bach']))
        
        c7, c8 = st.columns(2)
        try:
            bp = float(str(row.get(cols['base'])).replace(',',''))
            r65 = float(str(row.get("Population 65 years and over")).replace(',',''))
            c7.metric("Base Population", f"{bp:,.0f}")
            c8.metric("Elderly (65+)", f"{(r65/bp)*100:,.1f}%")
        except:
            c7.metric("Base Population", "N/A"); c8.metric("Elderly (65+)", "N/A")

        # ANCHORS
        st.markdown("<div class='section-label'>7 Nearest Strategic Assets</div>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_df = anchor_df.copy()
            a_df['dist'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
            t7 = a_df.sort_values('dist').head(7)
            tbl = "<table class='anchor-table'><tr><th>DIST</th><th>ASSET</th><th>TYPE</th></tr>"
            for _, a in t7.iterrows():
                tbl += f"<tr><td><b>{a['dist']:.1f}m</b></td><td>{a['name'].upper()}</td><td>{str(a.get('type','')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)

        st.divider()
        if st.button("EXECUTE STRATEGIC NOMINATION", type="primary", use_container_width=True):
            st.session_state.recom_count += 1
            st.success(f"Tract {sid} Nominated.")
            st.rerun()
    else:
        st.info("Select a green census tract on the map to load the Strategic Profile.")