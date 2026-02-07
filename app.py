import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM: EIG EDITORIAL + VIEWPORT OPTIMIZATION ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    /* Hero & Narrative Sections */
    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }
    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; max-width: 1100px; margin: 0 auto; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    .narrative-text { font-size: 1rem; line-height: 1.6; color: #94a3b8; margin-bottom: 20px; }
    
    /* Section 4: Compact Portal Styles */
    .portal-container { padding: 20px; background: #0b0f19; border-top: 2px solid #1e293b; }
    .metric-card { background: #161b28; padding: 10px; border: 1px solid #2d3748; border-radius: 4px; }
    .metric-label { font-size: 0.6rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 2px; }
    .metric-value { font-size: 1.15rem; font-weight: 900; color: #ffffff; }

    /* Indicator Pills */
    .indicator-pill { display: inline-block; padding: 3px 10px; border-radius: 4px; font-weight: 800; font-size: 0.65rem; margin-right: 4px; border: 1px solid #2d3748; }
    .active { background: #4ade80; color: #0b0f19; border-color: #4ade80; }
    .inactive { color: #475569; }

    /* Progress Footer */
    .progress-footer { position: fixed; bottom: 0; left: 0; width: 100%; background: #0b0f19; border-top: 1px solid #4ade80; padding: 10px 40px; z-index: 1000; display: flex; align-items: center; justify-content: space-between; }
    
    /* Tables */
    .stTable { font-size: 0.7rem !important; margin-top: -10px; }
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

if "recom_count" not in st.session_state: st.session_state.recom_count = 0

# --- SECTION 1: INTRODUCTION (EIG TONE) ---
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
            <div class='metric-label'>Basis Step-Up</div>
            <p style='font-size:0.8rem; color:#94a3b8;'>Benefit from a tiered basis step-up: urban investments receive targeted relief, while rural investments earn an enhanced basis step-up to incentivize high-impact parish projects.</p>
        </div>
        <div class='metric-card'>
            <div class='metric-label'>Permanent Exclusion</div>
            <p style='font-size:0.8rem; color:#94a3b8;'>Focus shift toward investment in rural tracts, rural healthcare facilities, Louisiana Main Street Districts, and digital infrastructure.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 3: OPPORTUNITY ZONE JUSTIFICATION ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>SECTION 3</div>
    <div class='section-title'>Opportunity Zone Justification Using Data</div>
""")

ex_c1, ex_c2 = st.columns(2)
with ex_c1:
    st.markdown("""
    <div class='metric-card' style='border-top: 4px solid #4ade80;'>
        <div class='metric-label'>Example A: Rural Healthcare Expansion</div>
        <p style='font-size:0.85rem; color:#cbd5e1; margin-top:10px;'>
            <b>Data:</b> High Poverty | < 50% Rural Broadband Access<br>
            <b>Asset:</b> Regional Transit Node (within 3 mi)<br>
            <b>Justification:</b> Utilizing the 2.0 rural healthcare priority, this investment funds a modernized clinic in a parish with high elderly populations, leveraging the basis step-up to offset construction costs in underserved areas.
        </p>
    </div>
    """, unsafe_allow_html=True)

with ex_c2:
    st.markdown("""
    <div class='metric-card' style='border-top: 4px solid #4ade80;'>
        <div class='metric-label'>Example B: Adaptive Reuse & Broadband Hub</div>
        <p style='font-size:0.85rem; color:#cbd5e1; margin-top:10px;'>
            <b>Data:</b> Deeply Distressed | Main Street District<br>
            <b>Asset:</b> Historic Municipal Building<br>
            <b>Justification:</b> This project revitalizes a historic Main Street structure into a multi-use hub. By integrating OZ 2.0 digital infrastructure incentives, the project finances high-speed fiber adaptive reuse for local small businesses.
        </p>
    </div>
    """, unsafe_allow_html=True)



st.markdown("</div>", unsafe_allow_html=True)

# --- SECTION 4: INTERACTIVE PORTAL (PLACEHOLDER) ---
st.markdown("<div class='portal-container'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div><p style='color:#64748b;'>Section 4 edits pending next response...</p></div>", unsafe_allow_html=True)