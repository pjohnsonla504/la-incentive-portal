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
        width: 100%; 
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
    .metric-card { background: #161b28; padding: 15px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; }
    .metric-label { font-size: 0.6rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 4px; }
    .metric-value { font-size: 1.15rem; font-weight: 900; color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    
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
        "pov": POV_COL, "base": "Estimate!!Total!!Population for whom poverty status is determined"
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
st.markdown("""
<div class='content-section'>
    <div class='section-num'>SECTION 2</div>
    <div class='section-title'>The Louisiana OZ 2.0 Framework</div>
    <div class='narrative-text'>
        The law provides a federal tax incentive for investors to re-invest their capital gains into Opportunity Funds, which are specialized vehicles dedicated to investing in designated low-income areas. 
        The One Big Beautiful Bill (OBBB) signed into law July 2025 will strengthen the program and make the tax incentive permanent. The OBBB ends the sunset clause, mandates new zone designations every ten years, 
        and directs capital toward distressed and rural communities.
    </div>
    
    <div style='display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom:30px;'>
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
            <p style='font-size:0.8rem; color:#94a3b8;'>Holding the investment for at least 10 years results in zero federal capital gains tax on appreciation, with a specific focus on rural health and digital infrastructure.</p>
        </div>
    </div>

    <div style='margin-bottom:15px; font-weight:800; font-size:0.85rem; color:#4ade80;'>OZ 2.0 DATA JUSTIFICATION USE-CASES</div>
""", unsafe_allow_html=True)

# Use-Cases Grid
uc1, uc2 = st.columns(2)
with uc1:
    st.markdown("""
    <div class='metric-card' style='border-left: 3px solid #4ade80;'>
        <div class='metric-label'>Use-Case: Rural Healthcare Facility</div>
        <p style='font-size:0.85rem; color:#cbd5e1;'>
            <b>Objective:</b> Modernize critical care facilities in parishes with high elderly populations and low labor participation.<br>
            <b>Justification:</b> Utilizing the 30% Rural Step-Up, this QROF investment offsets higher construction costs in remote areas while meeting the OBBB's rural equity mandate.
        </p>
    </div>
    """, unsafe_allow_html=True)
with uc2:
    st.markdown("""
    <div class='metric-card' style='border-left: 3px solid #4ade80;'>
        <div class='metric-label'>Use-Case: Historic Main Street Reuse</div>
        <p style='font-size:0.85rem; color:#cbd5e1;'>
            <b>Objective:</b> Adaptive reuse of historic Main Street assets for small business and fiber hubs.<br>
            <b>Justification:</b> Leveraging Louisiana Main Street designations to drive investment into core commercial districts, ensuring long-term permanent tax exclusion on asset appreciation.
        </p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)



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

# Map and Selection logic goes here
st.info("Interactive selection tool rendering in Section 4...")