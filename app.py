import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM: EIG EDITORIAL + FULL-WIDTH HEADERS ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    /* Full-Width Section Containers */
    .content-section { 
        padding: 40px 0; 
        border-bottom: 1px solid #1e293b; 
        width: 100%; /* Ensures header underline/width spans full container */
        margin: 0 auto; 
    }
    
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { 
        font-size: 2rem; 
        font-weight: 900; 
        margin-bottom: 15px; 
        letter-spacing: -0.02em; 
        display: block;
        width: 100%;
    }
    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }
    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
    .narrative-text { font-size: 1rem; line-height: 1.6; color: #94a3b8; margin-bottom: 20px; max-width: 1100px; }
    
    /* Metrics & Portal UI */
    .metric-card { background: #161b28; padding: 10px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; }
    .metric-label { font-size: 0.6rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 2px; }
    .metric-value { font-size: 1.15rem; font-weight: 900; color: #ffffff; }
    .indicator-pill { display: inline-block; padding: 3px 10px; border-radius: 4px; font-weight: 800; font-size: 0.65rem; margin-right: 4px; border: 1px solid #2d3748; }
    .active { background: #4ade80; color: #0b0f19; border-color: #4ade80; }
    .inactive { color: #475569; }

    /* Tables */
    .stTable { font-size: 0.7rem !important; margin-top: 5px; }
    thead tr th { background-color: #161b28 !important; color: #4ade80 !important; font-size: 0.6rem !important; padding: 4px !important; }
    tbody tr td { padding: 4px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
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

    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    df['pov_val'] = df[POV_COL].apply(clean)
    df['is_nmtc'] = df['pov_val'] >= 20.0
    df['is_deeply'] = (df['pov_val'] > 40.0) | (df[cols['unemp']].apply(clean) >= 10.5 if cols['unemp'] else False)

    # Tracks highlighted green are only those eligible for Opportunity Zone 2.0.
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else df['is_nmtc']
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

    a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {str(feat['properties'].get('GEOID')).zfill(11): {"lat": float(str(feat['properties'].get('INTPTLAT')).replace('+','')), "lon": float(str(feat['properties'].get('INTPTLON')).replace('+',''))} for feat in gj['features'] if 'INTPTLAT' in feat['properties']}
    for feat in gj['features']: feat['properties']['GEOID_MATCH'] = str(feat['properties'].get('GEOID')).zfill(11)

    return df, gj, a, centers, cols

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

# --- SECTION 1: INTRODUCTION ---
st.markdown("""
<div class='content-section' style='padding-top:80px;'>
    <div class='section-num'>SECTION 1</div>
    <div class='hero-subtitle'>Opportunity Zones 2.0</div>
    <div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Recommendation Portal</div>
    <div class='narrative-text'>
        The Opportunity Zones program is a federal initiative designed to drive long-term private investment into distressed communities by providing tax incentives to investors who reinvest their unrealized capital gains. It is a critical tool for bridging the "capital gap," ensuring that economic growth isn't confined to a few coastal hubs but reaches the heart of Louisiana’s parishes. By aligning private capital with community needs, the program fosters job creation, infrastructure development, and localized economic resilience.
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 2: THE LOUISIANA OZ 2.0 FRAMEWORK ---
st.markdown(f"""
<div class='content-section'>
    <div class='section-num'>SECTION 2</div>
    <div class='section-title'>The Louisiana OZ 2.0 Framework</div>
    <div class='narrative-text'>
        Similar to 1.0, holding the investment for at least 10 years results in zero federal capital gains tax on appreciation. OZ 2.0 streamlines these incentives to ensure <b>eligible</b> tracts receive the focused support they require.
    </div>
    <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;'>
        <div class='metric-card'>
            <div class='metric-label'>5-Year Rolling Deferral</div>
            <p style='font-size:0.8rem; color:#94a3b8;'>Investors can defer taxes on original capital gains through a 5-year rolling window, providing flexible liquidity for phased Louisiana developments.</p>
        </div>
        <div class='metric-card'>
            <div class='metric-label'>Basis Step-Up (Urban vs Rural)</div>
            <p style='font-size:0.8rem; color:#94a3b8;'>Standard QOFs receive a <b>10% basis step-up</b> after 5 years. Qualified Rural Funds (QROFs) receive an enhanced <b>30% basis step-up</b>, permanently excluding nearly a third of the original gain.</p>
        </div>
        <div class='metric-card'>
            <div class='metric-label'>Permanent Exclusion</div>
            <p style='font-size:0.8rem; color:#94a3b8;'>Focus shift toward investment in rural tracts, rural healthcare facilities, Louisiana Main Street Districts, and digital infrastructure.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 3: PLACEHOLDER ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>SECTION 3</div>
    <div class='section-title'>Opportunity Zone Justification Using Data</div>
    <p style='color:#475569;'><i>Section 3 content placeholder...</i></p>
</div>
""", unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>SECTION 4</div>
    <div class='section-title'>Strategic Selection Tool</div>
    <div class='narrative-text'>
        Identify high-conviction zones by selecting green eligible tracts. The profile panel will load specific socio-economic indicators and local anchor proximity.
    </div>
""", unsafe_allow_html=True)

map_col, profile_col = st.columns([0.45, 0.55], gap="medium")

with map_col:
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(255,255,255,0.02)"], [1, "#4ade80"]],
        showscale=False, marker_line_width=0.2, marker_line_color="#2d3748"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 30.8, "lon": -91.8}, zoom=5.8),
        height=550, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="selection_map")
    
    sid = None
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        sid = str(map_event["selection"]["points"][0]["location"]).zfill(11)

with profile_col:
    if sid:
        row = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        st.markdown(f"<h4 style='margin:0; font-size:1.3rem;'>TRACT {sid} <span style='color:#4ade80; font-size:0.9rem; margin-left:10px;'>{row.get('Parish', '').upper()} PARISH</span></h4>", unsafe_allow_html=True)
        
        m_val = str(row.get(cols['metro'], '')).lower()
        st.markdown(f"<div style='margin: 12px 0;'><span class='indicator-pill {'active' if 'metro' in m_val else 'inactive'}'>URBAN</span><span class='indicator-pill {'active' if 'rural' in m_val else 'inactive'}'>RURAL</span><span class='indicator-pill {'active' if row['is_nmtc'] else 'inactive'}'>NMTC</span><span class='indicator-pill {'active' if row['is_deeply'] else 'inactive'}'>DEEP DISTRESS</span></div>", unsafe_allow_html=True)

        r1, r2, r3, r4 = st.columns(4)
        r1.markdown(f"<div class='metric-card'><div class='metric-label'>Poverty</div><div class='metric-value'>{row.get(cols['pov'], 'N/A')}</div></div>", unsafe_allow_html=True)
        r2.markdown(f"<div class='metric-card'><div class='metric-label'>Unempl.</div><div class='metric-value'>{row.get(cols['unemp'], 'N/A')}</div></div>", unsafe_allow_html=True)
        # (Simplified metric logic for profile display)
        st.write("Metric data rendering...")
    else:
        st.markdown("<div style='padding: 150px 20px; text-align: center; background: #161b28; border: 1px dashed #2d3748; color:#64748b; border-radius:4px;'>Select an eligible (green) tract on the map to load the demographic profile.</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)