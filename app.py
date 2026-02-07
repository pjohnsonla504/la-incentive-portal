import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM: a16z EDITORIAL STYLE ---
st.set_page_config(page_title="Louisiana American Dynamism", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    /* Hero & Typography */
    .hero-title { font-family: 'Playfair Display', serif; font-size: 5rem; font-weight: 900; line-height: 0.9; margin-bottom: 20px; color: #ffffff; }
    .hero-subtitle { font-size: 1.2rem; color: #4ade80; font-weight: 800; letter-spacing: 0.1em; text-transform: uppercase; margin-bottom: 40px; }
    
    /* Content Blocks */
    .content-section { padding: 80px 0; border-bottom: 1px solid #1e293b; max-width: 1100px; margin: 0 auto; }
    .section-num { font-size: 1rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; }
    .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 30px; letter-spacing: -0.02em; }
    .narrative-text { font-size: 1.25rem; line-height: 1.7; color: #94a3b8; margin-bottom: 25px; }
    
    /* Metrics Split View */
    .metric-card { background: #161b28; padding: 20px; border: 1px solid #2d3748; border-radius: 4px; }
    .metric-label { font-size: 0.75rem; color: #4ade80; font-weight: 800; text-transform: uppercase; }
    .metric-value { font-size: 1.8rem; font-weight: 900; color: #ffffff; margin-top: 5px; }

    /* Indicator Pills */
    .indicator-pill { display: inline-block; padding: 6px 16px; border-radius: 50px; font-weight: 800; font-size: 0.8rem; margin-right: 8px; border: 1px solid #2d3748; }
    .active { background: #4ade80; color: #0b0f19; border-color: #4ade80; }
    .inactive { color: #64748b; }

    /* Progress Footer */
    .progress-footer { position: fixed; bottom: 0; left: 0; width: 100%; background: #0b0f19; border-top: 1px solid #4ade80; padding: 15px 40px; z-index: 1000; display: flex; align-items: center; justify-content: space-between; }
    
    /* Tables */
    .stTable { background: transparent !important; }
    thead tr th { background-color: #161b28 !important; color: #4ade80 !important; font-size: 0.7rem !important; text-transform: uppercase !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master Files
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

    # Standardize GEOID
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    # Logic for Highlighting
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    df['pov_val'] = df[POV_COL].apply(clean)
    df['is_nmtc'] = df['pov_val'] >= 20.0
    df['is_deeply'] = (df['pov_val'] > 40.0) | (df[cols['unemp']].apply(clean) >= 10.5 if cols['unemp'] else False)

    # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0.
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else df['is_nmtc']
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

    # Assets & GeoJSON
    a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {str(feat['properties'].get('GEOID')).zfill(11): {"lat": float(str(feat['properties'].get('INTPTLAT')).replace('+','')), "lon": float(str(feat['properties'].get('INTPTLON')).replace('+',''))} for feat in gj['features'] if 'INTPTLAT' in feat['properties']}
    for feat in gj['features']: feat['properties']['GEOID_MATCH'] = str(feat['properties'].get('GEOID')).zfill(11)

    return df, gj, a, centers, cols

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

# --- 3. THE NARRATIVE FLOW ---

# SECTION 1: INTRODUCTION
st.markdown("""
<div class='content-section' style='padding-top:120px;'>
    <div class='hero-subtitle'>American Dynamism</div>
    <div class='hero-title'>Louisiana<br>Strategic Portals</div>
    <div class='narrative-text'>
        The 2026 American Dynamism initiative focuses on the intersection of industrial capacity, human capital, 
        and institutional stability. By aligning federal tax incentives with state-level assets, 
        we create a roadmap for long-term regional prosperity.
    </div>
</div>
""", unsafe_allow_html=True)

# SECTION 2: THE PROGRAM DEFINITION (OEDIT MODEL)
st.markdown(f"""
<div class='content-section'>
    <div class='section-num'>02</div>
    <div class='section-title'>Program Definition</div>
    <div class='narrative-text'>
        Modeled after the <b>Colorado Opportunity Zone Program</b>, this framework is a federal economic development tool 
        that encourages long-term private investment in designated low-income census tracts.
    </div>
    <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 30px;'>
        <div class='metric-card'><div class='metric-label'>Deferral</div><p style='font-size:0.9rem; color:#94a3b8;'>Investors can defer tax on prior capital gains until 2026 or until the investment is sold.</p></div>
        <div class='metric-card'><div class='metric-label'>Elimination</div><p style='font-size:0.9rem; color:#94a3b8;'>Investments held for at least 10 years are exempt from capital gains taxes on appreciation.</p></div>
        <div class='metric-card'><div class='metric-label'>Strategic Focus</div><p style='font-size:0.9rem; color:#94a3b8;'>Nomination is restricted to the top 25% of eligible low-income tracts to ensure capital concentration.</p></div>
    </div>
</div>
""", unsafe_allow_html=True)

# SECTION 3: DATA INTERPRETATION (EXAMPLE CASE)
st.markdown("""
<div class='content-section'>
    <div class='section-num'>03</div>
    <div class='section-title'>Interpreting the Data</div>
    <div class='narrative-text'>
        Justification for OZ nomination is found where <b>Human Capital Metrics</b> meet <b>Infrastructural Assets</b>. 
    </div>
    <div class='metric-card' style='border-left: 4px solid #4ade80;'>
        <p style='margin:0; font-size:1.1rem;'><b>The Justification Example:</b> A tract with <b>40%+ Poverty</b> (Deeply Distressed) but located within <b>2 miles of a Port</b> and a <b>Community College</b> creates a high-ROI case. The distressed labor pool provides the workforce for industrial expansion, while the OZ status provides the non-dilutive capital to build the facilities.</p>
    </div>
</div>
""", unsafe_allow_html=True)

# SECTION 4: THE STRATEGIC RECOMMENDATION MAP (40/60 Split)
st.markdown("<div class='content-section'><div class='section-num'>04</div><div class='section-title'>Strategic Selection</div>", unsafe_allow_html=True)

map_col, profile_col = st.columns([0.4, 0.6], gap="large")

with map_col:
    # Tracks highlighted green are only those eligible for Opportunity Zone 2.0
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(255,255,255,0.02)"], [1, "#4ade80"]],
        showscale=False, marker_line_width=0.2, marker_line_color="#2d3748"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 30.8, "lon": -91.8}, zoom=6.2),
        height=800, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="selection_map")
    
    sid = None
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        sid = str(map_event["selection"]["points"][0]["location"]).zfill(11)

with profile_col:
    if sid:
        row = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        st.markdown(f"<div style='margin-bottom:20px;'><h2 style='margin:0;'>TRACT {sid}</h2><p style='color:#4ade80; font-weight:800;'>{row.get('Parish', '').upper()} PARISH</p></div>", unsafe_allow_html=True)
        
        # QUALIFICATION INDICATORS
        m_val = str(row.get(cols['metro'], '')).lower()
        st.markdown(f"""
            <div style='margin-bottom:30px;'>
                <span class='indicator-pill {'active' if 'metro' in m_val else 'inactive'}'>URBAN</span>
                <span class='indicator-pill {'active' if 'rural' in m_val else 'inactive'}'>RURAL</span>
                <span class='indicator-pill {'active' if row['is_nmtc'] else 'inactive'}'>NMTC</span>
                <span class='indicator-pill {'active' if row['is_deeply'] else 'inactive'}'>DEEPLY DISTRESSED</span>
            </div>
        """, unsafe_allow_html=True)

        # 8 METRIC CARDS
        def f_val(c, is_p=True, is_d=False):
            v = row.get(c, 0)
            try:
                num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
                return f"${num:,.0f}" if is_d else (f"{num:,.1f}%" if is_p else f"{num:,.0f}")
            except: return "N/A"

        c1, c2 = st.columns(2)
        with c1: 
            st.markdown(f"<div class='metric-card'><div class='metric-label'>Poverty</div>