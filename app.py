import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    .profile-header { background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #4ade80; margin-bottom: 20px; }
    .header-item { display: inline-block; margin-right: 30px; }
    .header-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; font-weight: 700; display: block; }
    .header-value { color: #ffffff; font-size: 1.1rem; font-weight: 800; }
    .stProgress > div > div > div > div { background-color: #4ade80; }
    
    /* Metrics & Indicators */
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.4rem !important; font-weight: 800; }
    .indicator-box { border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 10px; border: 2px solid #475569; height: 90px; display: flex; flex-direction: column; justify-content: center; }
    .status-yes { background-color: rgba(74, 222, 128, 0.2); border-color: #4ade80 !important; }
    .status-no { background-color: rgba(30, 41, 59, 0.5); border-color: #334155 !important; opacity: 0.6; }
    .indicator-label { font-size: 0.7rem; color: #ffffff; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 1rem; font-weight: 900; color: #ffffff; margin-top: 3px; }
    
    .section-label { color: #94a3b8; font-size: 0.85rem; font-weight: 800; margin-top: 15px; border-bottom: 1px solid #334155; padding-bottom: 5px; text-transform: uppercase; }
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 10px; }
    .anchor-table td { padding: 6px; border-bottom: 1px solid #334155; color: #f1f5f9; }
    .anchor-table th { text-align: left; color: #94a3b8; font-size: 0.75rem; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master CSV
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Static Column Mappings
    POV_RATE_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    POV_BASE_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
    # Resilient Column Finders
    def find_col(keywords):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keywords): return col
        return None

    unemp_col = find_col(['unemployment', 'rate'])
    mfi_col = find_col(['median', 'family', 'income']) or find_col(['median', 'household', 'income'])
    metro_col = find_col(['metro', 'status'])
    edu_hs = find_col(['hs', 'degree']) or find_col(['high', 'school'])
    edu_bach = find_col(['bachelor'])
    labor_col = find_col(['labor', 'force'])
    home_val = find_col(['median', 'home', 'value'])

    # Standardize GEOID for Map Matching
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # Calculated Booleans
    df['is_nmtc_eligible'] = df[POV_RATE_COL].apply(clean) >= 20.0 if POV_RATE_COL in df.columns else False
    df['is_deeply'] = (df[POV_RATE_COL].apply(clean) > 40.0) | (df[unemp_col].apply(clean) >= 10.5 if unemp_col else False)
    
    # Highlighted Green (Explicit Instruction)
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else False
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

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
        "pov_rate": POV_RATE_COL, "pov_base": POV_BASE_COL, "unemp": unemp_col, "mfi": mfi_col,
        "metro": metro_col, "hs": edu_hs, "bach": edu_bach, "labor": labor_col, "home": home_val
    }

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

# --- 3. STATE ---
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None
if "recom_count" not in st.session_state: st.session_state.recom_count = 0

# --- 4. INTERFACE ---
col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(255,255,255,0.05)"], [1, "rgba(74, 222, 128, 0.7)"]],
        showscale=False, marker_line_width=0.5, marker_line_color="#475569"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 31.0, "lon": -91.8}, zoom=6.2),
        height=1020, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="main_map")
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        st.rerun()

with col_side:
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
        
        # 1. Urban/Rural & NMTC Indicators
        st.markdown("<div class='section-label'>Qualification Indicators</div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m_val = str(row.get(cols['metro'], '')).lower()
        with m1: st.markdown(f"<div class='indicator-box {'status-yes' if 'metro' in m_val else 'status-no'}'><div class='indicator-label'>Urban</div><div class='indicator-value'>{'YES' if 'metro' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='indicator-box {'status-yes' if 'rural' in m_val else 'status-no'}'><div class='indicator-label'>Rural</div><div class='indicator-value'>{'YES' if 'rural' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc_eligible'] else 'status-no'}'><div class='indicator-label'>NMTC</div><div class='indicator-value'>{'YES' if row['is_nmtc_eligible'] else 'NO'}</div></div>", unsafe_allow_html=True)
        with m4: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_deeply'] else 'status-no'}'><div class='indicator-label'>Deeply Dist.</div><div class='indicator-value'>{'YES' if row['is_deeply'] else 'NO'}</div></div>", unsafe_allow_html=True)

        # 2. 8 Demographic Metrics
        st.markdown("<div class='section-label'>Economic & Human Capital</div>", unsafe_allow_html=True)
        d1, d2, d3, d4 = st.columns(4)
        d5, d6, d7, d8 = st.columns(4)
        
        def f_val(c, is_p=True, is_d=False):
            v = row.get(c, 0)
            try:
                num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
                if is_d: return f"${num:,.0f}"
                return f"{num:,.1f}%" if is_p else f"{num:,.0f}"
            except: return "N/A"

        d1.metric("Poverty Rate", f_val(cols['pov_rate']))
        d2.metric("Unemployment", f_val(cols['unemp']))
        d3.metric("Labor Part.", f_val(cols['labor']))
        d4.metric("Home Value", f_val(cols['home'], False, True))
        d5.metric("HS Grad+", f_val(cols['hs']))
        d6.metric("Bach. Degree", f_val(cols['bach']))
        
        # Base Pop Calc
        try:
            bp = float(str(row.get(cols['pov_base'])).replace(',',''))
            r65 = float(str(row.get("Population 65 years and over")).replace(',',''))
            d7.metric("Base Pop", f"{bp:,.0f}")
            d8.metric("Elderly 65+", f"{(r65/bp)*100:,.1f}%")
        except:
            d7.metric("Base Pop", "N/A"); d8.metric("Elderly 65+", "N/A")

        # 3. 7 Nearest Anchors
        st.markdown("<div class='section-label'>7 Nearest Strategic Assets</div>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_df = anchor_df.copy()
            a_df['dist'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
            t7 = a_df.sort_values('dist').head(7)
            tbl = "<table class='anchor-table'><tr><th>DIST</th><th>ASSET NAME</th><th>TYPE</th></tr>"
            for _, a in t7.iterrows():
                tbl += f"<tr><td><b>{a['dist']:.1f}m</b></td><td>{a['name'].upper()}</td><td>{str(a.get('type','')).upper()}</td></tr>"
            st.markdown(tbl + "</table>", unsafe_allow_html=True)

        st.divider()
        st.subheader("STRATEGIC NOMINATION")
        if st.button("EXECUTE NOMINATION", type="primary"):
            st.session_state.recom_count += 1
            st.success("Tract Nominated Successfully.")
    else:
        st.info("Select a green census tract on the map to load the Strategic Profile.")