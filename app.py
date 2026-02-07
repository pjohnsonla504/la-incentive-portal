import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM: FULL-WIDTH GRID & EIG EDITORIAL ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    /* Standardized Section Containers */
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
    
    /* Grid & Cards */
    .metric-grid {
        display: flex;
        gap: 20px;
        margin-bottom: 30px;
        width: 100%;
    }
    .metric-card { 
        flex: 1;
        background: #161b28; 
        padding: 20px; 
        border: 1px solid #2d3748; 
        border-radius: 4px; 
    }
    .metric-label { font-size: 0.65rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 8px; }
    .metric-value { font-size: 1.15rem; font-weight: 900; color: #ffffff; margin-bottom: 10px; }
    .card-text { font-size: 0.8rem; color: #94a3b8; line-height: 1.5; }
    
    /* Indicator UI for Selection Tool */
    .indicator-pill { display: inline-block; padding: 3px 10px; border-radius: 4px; font-weight: 800; font-size: 0.65rem; margin-right: 4px; border: 1px solid #2d3748; }
    .active { background: #4ade80; color: #0b0f19; border-color: #4ade80; }
    .inactive { color: #475569; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    # Placeholder for logic loading 'Opportunity Zones 2.0 - Master Data File.csv'
    # Tracks highlighted green are only those eligible for Opportunity Zone 2.0.
    return pd.DataFrame(), {}, pd.DataFrame(), {}, {}

# --- SECTION 1: INTRODUCTION ---
st.markdown("""
<div class='content-section' style='padding-top:80px;'>
    <div class='section-num'>SECTION 1</div>
    <div class='hero-subtitle'>Opportunity Zones 2.0</div>
    <div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Recommendation Portal</div>
    <div class='narrative-text'>
        The Opportunity Zones program is a federal initiative designed to drive long-term private investment into distressed communities by providing tax incentives to investors who reinvest their unrealized capital gains. It is a critical tool for bridging the "capital gap," ensuring that economic growth isn't confined to a few coastal hubs but reaches the heart of Louisiana’s parishes.
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
    
    <div class='metric-grid'>
        <div class='metric-card'>
            <div class='metric-label'>Rolling Deferral</div>
            <div class='metric-value'>5-Year Window</div>
            <div class='card-text'>Investors can defer taxes on original capital gains through a 5-year rolling window, providing flexible liquidity for phased Louisiana developments.</div>
        </div>
        <div class='metric-card'>
            <div class='metric-label'>Basis Step-Up</div>
            <div class='metric-value'>10% Urban / 30% Rural</div>
            <div class='card-text'>Standard QOFs receive a 10% step-up. Qualified Rural Funds (QROFs) receive an enhanced 30% step-up, permanently excluding nearly a third of the original gain.</div>
        </div>
        <div class='metric-card'>
            <div class='metric-label'>Permanent Exclusion</div>
            <div class='metric-value'>10-Year Hold</div>
            <div class='card-text'>Holding the investment for at least 10 years results in zero federal capital gains tax on appreciation, with a specific focus on rural health and digital infrastructure.</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# --- SECTION 3: DATA JUSTIFICATION USE-CASES ---
st.markdown("""
<div class='content-section'>
    <div class='section-num'>SECTION 3</div>
    <div class='section-title'>Opportunity Zone Justification Using Data</div>
    <div class='narrative-text'>
        Strategic deployment requires aligning demographic distress with community assets. Below are two model justifications for how OZ 2.0 capital can be targeted.
    </div>
</div>
""", unsafe_allow_html=True)

uc1, uc2 = st.columns(2)
with uc1:
    st.markdown("""
    <div class='metric-card' style='border-left: 4px solid #4ade80; margin-top:20px;'>
        <div class='metric-label'>Case Study: Rural Healthcare</div>
        <div class='card-text'>
            <b>Objective:</b> Modernize critical care facilities in parishes with high elderly populations.<br><br>
            <b>Data Justification:</b> Utilizing the 30% Rural Step-Up, this QROF investment offsets higher construction costs in remote areas while meeting the OBBB's rural equity mandate.
        </div>
    </div>
    """, unsafe_allow_html=True)
with uc2:
    st.markdown("""
    <div class='metric-card' style='border-left: 4px solid #4ade80; margin-top:20px;'>
        <div class='metric-label'>Case Study: Main Street Reuse</div>
        <div class='card-text'>
            <b>Objective:</b> Adaptive reuse of historic Main Street assets for small business and fiber hubs.<br><br>
            <b>Data Justification:</b> Leveraging Louisiana Main Street designations to drive investment into core commercial districts, ensuring long-term permanent tax exclusion.
        </div>
    </div>
    """, unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("""
<div class='content-section' style='margin-top:40px;'>
    <div class='section-num'>SECTION 4</div>
    <div class='section-title'>Strategic Selection Tool</div>
    <div class='narrative-text'>
        Identify high-conviction zones by selecting green eligible tracts. The profile panel will load specific socio-economic indicators and local anchor proximity.
    </div>
</div>
""", unsafe_allow_html=True)

# Interactive Map & Data Profile Logic would begin here
st.info("Interactive Section 4 is active below.")