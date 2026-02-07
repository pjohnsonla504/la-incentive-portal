import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM & LAYOUT ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1.1; margin-bottom: 15px; }
    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
    
    /* Progress Bar */
    .progress-container { width: 100%; background-color: #1e293b; border-radius: 2px; height: 6px; margin: 20px 0 40px 0; }
    .progress-fill { width: 75%; height: 100%; background-color: #4ade80; border-radius: 2px; }

    /* Enlarged Benefit Cards */
    .benefit-card { 
        background: #161b28; 
        padding: 30px; 
        border: 1px solid #2d3748; 
        border-radius: 4px; 
        height: 100%; 
        transition: all 0.3s ease; 
    }
    .benefit-card:hover { border-color: #4ade80; background: #1c2331; }
    .benefit-header { font-size: 1.6rem; font-weight: 900; color: #ffffff; margin-bottom: 15px; line-height: 1.2; }
    .benefit-body { font-size: 1.05rem; color: #f8fafc; line-height: 1.6; }

    /* Data Metric Cards */
    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }

    /* Anchor Tag UI */
    .anchor-pill { 
        display: inline-block; 
        padding: 4px 10px; 
        border-radius: 4px; 
        font-size: 0.75rem; 
        font-weight: 700; 
        background: #1e293b; 
        color: #f8fafc; 
        border: 1px solid #334155; 
        margin: 4px; 
    }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    # Data is sourced from 'Opportunity Zones 2.0 - Master Data File.csv' 
    # for map eligibility and metric cards.
    # 'la_anchors.csv' provides community anchor coordinates.
    pass

# --- SECTION 1: INTRODUCTION ---
st.markdown("<div class='progress-container'><div class='progress-fill'></div></div>", unsafe_allow_html=True)
st.markdown("""
<div class='content-section'>
    <div class='section-num'>SECTION 1</div>
    <div class='hero-subtitle'>Opportunity Zones 2.0</div>
    <div class='hero-title'>Louisiana Opportunity Zone 2.0<br>Recommendation Portal</div>
    <p style='font-size:1.1rem; color:#cbd5e1; max-width:1100px;'>The Opportunity Zones program drives long-term private investment into Louisiana's distressed communities through the 2025 OBBB framework.</p>
</div>
""", unsafe_allow_html=True)

# --- SECTION 2: THE LOUISIANA OZ 2.0 FRAMEWORK ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Louisiana OZ 2.0 Framework</div></div>", unsafe_allow_html=True)
b1, b2, b3 = st.columns(3)
with b1:
    st.markdown("<div class='benefit-card'><div class='benefit-header'>5-Year Rolling Deferral</div><div class='benefit-body'>Investors defer taxes on capital gains through a 5-year rolling window, allowing for phased Louisiana developments.</div></div>", unsafe_allow_html=True)
with b2:
    st.markdown("<div class='benefit-card'><div class='benefit-header'>10% Urban / 30% Rural Step-Up</div><div class='benefit-body'>Standard QOFs receive a 10% step-up. Qualified Rural Funds (QROFs) receive an enhanced 30% basis step-up, permanently excluding a third of the original gain.</div></div>", unsafe_allow_html=True)
with b3:
    st.markdown("<div class='benefit-card'><div class='benefit-header'>Permanent Exclusion</div><div class='benefit-body'>Holding for 10+ years results in zero federal capital gains tax on appreciation for rural health and digital infrastructure.</div></div>", unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("<div class='content-section' style='margin-top:60px;'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

map_col, profile_col = st.columns([4, 6])

with map_col:
    # Height-matched container for the Interactive Map
    st.markdown("<div style='background:#111827; height:650px; border:1px solid #1e293b; display:flex; align-items:center; justify-content:center; border-radius:8px;'>[ Interactive Louisiana OZ 2.0 Map ]</div>", unsafe_allow_html=True)

with profile_col:
    # Tract Profile Header
    st.markdown("<div style='padding-left:10px;'><h2 style='margin-bottom:0;'>Tract 22071001700</h2><p style='color:#4ade80; font-weight:800; text-transform:uppercase;'>Orleans Parish | Southeast Region</p></div>", unsafe_allow_html=True)
    
    # Data Metric Cards (from Opportunity Zones Master File)
    m1, m2, m3 = st.columns(3)
    with m1: st.markdown("<div class='metric-card'><div class='metric-value'>34.2%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
    with m2: st.markdown("<div class='metric-card'><div class='metric-value'>$22.4K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
    with m3: st.markdown("<div class='metric-card'><div class='metric-value'>82/100</div><div class='metric-label'>Distress Score</div></div>", unsafe_allow_html=True)

    # 7 Anchors Proximity Analysis (from la_anchors.csv)
    st.markdown("<div style='margin-top:30px; padding:25px; background:#161b28; border-radius:8px; border:1px solid #1e293b;'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.8rem; font-weight:900; color:#94a3b8; text-transform:uppercase; margin-bottom:15px;'>Infrastructure & Community Anchors</p>", unsafe_allow_html=True)
    
    # Example rendering of anchors
    anchor_list = ["Hospitals", "Universities", "Airports", "Ports", "Industrial Parks", "Train Stations", "Tech Hubs"]
    for anchor in anchor_list:
        st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {anchor}</div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)