import streamlit as st

import pandas as pd

import plotly.graph_objects as go

import json

import numpy as np



# --- 1. DESIGN SYSTEM: ENHANCED TYPOGRAPHY ---

st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")



st.markdown("""

    <style>

    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');

    

    html, body, [class*="stApp"] {

        font-family: 'Inter', sans-serif;

        background-color: #0b0f19;

        color: #ffffff;

    }



    .content-section { 

        padding: 40px 0; 

        border-bottom: 1px solid #1e293b; 

        width: 100%; 

        margin: 0 auto; 

    }

    

    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }

    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; display: block; width: 100%; }

    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }

    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }

    .narrative-text { font-size: 1.1rem; line-height: 1.6; color: #cbd5e1; margin-bottom: 25px; max-width: 1100px; }

    

    /* Enhanced Benefit Box Styling */

    .benefit-card { 

        background: #161b28; 

        padding: 30px; 

        border: 1px solid #2d3748; 

        border-radius: 4px; 

        height: 100%;

        transition: all 0.3s ease;

    }

    .benefit-card:hover { border-color: #4ade80; background: #1c2331; }

    

    .benefit-label { font-size: 0.8rem; color: #4ade80; font-weight: 900; text-transform: uppercase; margin-bottom: 12px; letter-spacing: 0.05em; }

    .benefit-header { font-size: 1.6rem; font-weight: 900; color: #ffffff; margin-bottom: 15px; line-height: 1.2; }

    .benefit-body { font-size: 1.05rem; color: #f8fafc; line-height: 1.6; font-weight: 400; }



    /* Indicator UI */

    .indicator-pill { display: inline-block; padding: 4px 12px; border-radius: 4px; font-weight: 800; font-size: 0.7rem; margin-right: 5px; border: 1px solid #2d3748; }

    .active { background: #4ade80; color: #0b0f19; border-color: #4ade80; }

    </style>

    """, unsafe_allow_html=True)



# --- 2. DATA ENGINE ---

@st.cache_data(ttl=60)

def load_data():

    # Tracks highlighted green are only those eligible for Opportunity Zone 2.0.

    # [Internal Note: Ensure 'Opportunity Zones 2.0 - Master Data File.csv' is in path]

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

</div>

""", unsafe_allow_html=True)



# Enlarged Benefit Boxes

b1, b2, b3 = st.columns(3)

with b1:

    st.markdown("""

    <div class='benefit-card'>

        <div class='benefit-label'>Benefit 01</div>

        <div class='benefit-header'>5-Year Rolling Deferral</div>

        <div class='benefit-body'>Investors can defer taxes on original capital gains through a 5-year rolling window, providing flexible liquidity for phased Louisiana developments.</div>

    </div>

    """, unsafe_allow_html=True)

with b2:

    st.markdown("""

    <div class='benefit-card'>

        <div class='benefit-label'>Benefit 02</div>

        <div class='benefit-header'>10% Urban / 30% Rural Step-Up</div>

        <div class='benefit-body'>Standard QOFs receive a 10% basis step-up after 5 years. Qualified Rural Funds (QROFs) receive an enhanced 30% basis step-up, permanently excluding nearly a third of the original gain.</div>

    </div>

    """, unsafe_allow_html=True)

with b3:

    st.markdown("""

    <div class='benefit-card'>

        <div class='benefit-label'>Benefit 03</div>

        <div class='benefit-header'>Permanent Exclusion</div>

        <div class='benefit-body'>Holding the investment for at least 10 years results in zero federal capital gains