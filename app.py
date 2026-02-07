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
    
    /* Profile Header */
    .profile-header { background-color: #1e293b; padding: 20px; border-radius: 12px; border-left: 8px solid #22c55e; margin-bottom: 25px; color: white; }
    .header-item { display: inline-block; margin-right: 40px; }
    .header-label { color: #94a3b8; font-size: 0.85rem; text-transform: uppercase; font-weight: 700; display: block; }
    .header-value { color: #ffffff; font-size: 1.3rem; font-weight: 800; }

    /* Large Metric Cards */
    [data-testid="stMetricValue"] { 
        color: #ffffff !important; 
        font-size: 1.8rem !important; 
        font-weight: 800 !important; 
    }
    [data-testid="stMetricLabel"] { 
        color: #cbd5e1 !important; 
        font-weight: 700 !important; 
        font-size: 0.9rem !important;
        text-transform: uppercase;
    }
    [data-testid="stMetric"] { 
        background-color: #334155; 
        border-radius: 12px; 
        padding: 20px !important; 
        border: 1px solid #475569;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    
    /* Indicators */
    .indicator-box { border-radius: 10px; padding: 15px; text-align: center; margin-bottom: 12px; border: 2px solid #e2e8f0; height: 100px; display: flex; flex-direction: column; justify-content: center; background: white; }
    .status-yes { background-color: #dcfce7; border-color: #22c55e !important; color: #166534; }
    .status-no { background-color: #f1f5f9; border-color: #cbd5e1 !important; opacity: 0.7; color: #64748b; }
    .indicator-label { font-size: 0.75rem; text-transform: uppercase; font-weight: 800; }
    .indicator-value { font-size: 1.2rem; font-weight: 900; margin-top: 5px; }
    
    .section-label { color: #475569; font-size: 1rem; font-weight: 800; margin-top: 25px; border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; text-transform: uppercase; letter-spacing: 0.05em; }
    
    /* Anchors Table */
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.95rem; background: white; border-radius: 8px; overflow: hidden; }
    .anchor-table td { padding: 12px; border-bottom: 1px solid #f1f5f9; color: #1e293b; }
    .anchor-table th { background: #f8fafc; text-align: left; color: #64748b; padding: 12px; font-size: 0.8rem; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    POV_RATE_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    POV_BASE_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
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

    # Standardize GEOID
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # NMTC Logic
    df['is_nmtc_eligible'] = df[POV_RATE_COL].apply(clean) >= 20.0 if POV_RATE_COL in df.columns else False
    df['is_deeply'] = (df[POV_RATE_COL].apply(clean) > 40.0) | (df[unemp_col].apply(clean) >= 10.5 if unemp_col else False)
    
    # ELIGIBLE ONLY = GREEN
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else False
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

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

# --- 4. INTERFACE ---
col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(255,255,255,0)"], [1, "rgba(34, 197, 94, 0.75)"]],
        showscale=False, marker_line_width=0.8, marker_line_color="#1e293b"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 31.0, "lon": -91.8}, zoom=6.5),
        height=1020, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="map_v63")
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        st.rerun()

with col_side:
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
        
        st.markdown("<div class='section-label'>Program Qualifications</div>", unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m_val = str(row.get(cols['metro'], '')).lower()
        with m1: st.markdown(f"<div class='indicator-box {'status-yes' if 'metro' in m_val else 'status-no'}'><div class='indicator-label'>Urban</div><div class='indicator-value'>{'YES' if 'metro' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m2: st.markdown(f"<div class='indicator-box {'status-yes' if 'rural' in m_val else 'status-no'}'><div class='indicator-label'>Rural</div><div class='indicator-value'>{'YES' if 'rural' in m_val else 'NO'}</div></div>", unsafe_allow_html=True)
        with m3: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc_eligible'] else 'status-no'}'><div class='indicator-label'>NMTC</div><div class='indicator-value'>{'YES' if row['is_nmtc_eligible'] else 'NO'}</div></div>", unsafe_allow_html=True)
        with m4: st.markdown(f"<div class='indicator-box {'status-yes' if row['is_deeply'] else 'status-no'}'><div class='indicator-label'>Deeply Dist.</div><div class='indicator-value'>{'YES' if row['is_deeply'] else 'NO'}</div></div>", unsafe_allow_html=True)

        st.markdown("<div class='section-label'>Economic & Demographic Profile</div>", unsafe_allow_html=True)
        def f_val(c, is_p=True, is_d=False):
            v = row.get(c, 0)
            try:
                num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
                if is_d: return f"${num:,.0f}"
                return f"{num:,.1f}%" if is_p else f"{num:,.0f}"
            except: