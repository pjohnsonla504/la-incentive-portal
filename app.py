import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | American Dynamism", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #050a14; color: #ffffff; }
    
    /* Demographic Metric Titles - White */
    [data-testid="stMetricLabel"] { 
        font-size: 0.8rem !important; 
        text-transform: uppercase; 
        color: #ffffff !important; 
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    /* Demographic Metric Numbers - Green */
    [data-testid="stMetricValue"] { 
        font-size: 1.4rem !important; 
        font-weight: 700 !important; 
        color: #00ff88 !important; 
    }
    
    .stMetric { 
        background-color: #0f172a; 
        padding: 10px; 
        border-radius: 4px; 
        border: 1px solid #1e293b; 
    }
    
    /* 2x2 Indicator Cards */
    .indicator-box {
        border-radius: 4px;
        padding: 12px;
        text-align: center;
        margin-bottom: 10px;
        border: 1px solid #334155;
    }
    .status-yes { background-color: rgba(0, 255, 136, 0.15); border-color: #00ff88; }
    .status-no { background-color: #1e293b; border-color: #334155; opacity: 0.6; }
    
    .indicator-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;}
    .indicator-value { font-size: 0.9rem; font-weight: bold;}
    .val-yes { color: #00ff88; }
    .val-no { color: #64748b; }
    
    .anchor-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    .anchor-table th { text-align: left; color: #ffffff; border-bottom: 1px solid #334155; padding: 8px; }
    .anchor-table td { padding: 8px; border-bottom: 1px solid #0f172a; color: #94a3b8; }
    </style>
    """, unsafe_allow_html=True)

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"System Link Failure: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- 2. DATA UTILITIES ---
def calculate_distance(lat1, lon1, lat2, lon2):
    try:
        r = 3958.8 
        p1, p2 = np.radians(float(lat1)), np.radians(float(lat2))
        dp, dl = np.radians(float(lat2)-float(lat1)), np.radians(float(lon2)-float(lon1))
        a = np.sin(dp/2)**2 + np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
        return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
    except: return 999.0

def safe_num(val, is_money=False):
    try:
        if pd.isna(val) or str(val).strip().lower() in ['n/a', 'nan', '']: return "N/A"
        n = float(str(val).replace('$', '').replace(',', '').replace('%', '').strip())
        if is_money: return f"${n:,.0f}"
        if n <= 100 and n > 0: return f"{n:,.1f}%"
        return f"{n:,.0f}"
    except: return "N/A"

@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    try:
        a = pd.read_csv("la_anchors.csv")
    except:
        a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    df['map_status'] = np.where(df['5-year ACS Eligiblity'].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']), 1, 0)

    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        p = feat['properties']
        gid = str(p.get('GEOID', '')).split('.')[0][-11:].zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        lat, lon = p.get('INTPTLAT'), p.get('INTPTLON')
        if lat and lon:
            centers[gid] = {"lat": float(str(lat).replace('+', '')), "lon": float(str(lon).replace('+', ''))}

    m_map = {
        "home": "Median Home Value", "dis": "Disability Population (%)",
        "pop65": "Population 65 years and over", "labor": "Labor Force Participation (%)",
        "unemp": "Unemployment Rate (%)", "hs": "HS Degree or More (%)",
        "bach": "Bachelor's Degree or More (%)", "web": "Broadband Internet (%)"
    }
    return df, gj, a, m_map, centers

master_df, la_geojson, anchor_df, M_MAP, tract_centers = load_data()

# --- 3. INTERFACE ---
st.title(f"Strategic Portal: {st.session_state.get('a_val', 'Louisiana')}")

col_map, col_side = st.columns([0.5, 0.5])

with col_side:
    sid = st.session_state["selected_tract"]
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"<h3 style='color:#00ff88; margin-top:0;'>TRACT {sid} | {row.get('Parish')}</h3>", unsafe_allow_html=True)
        
        def get_ind_html(label, value_str):
            is_yes = False
            if "Urban" in label: is_yes = 'urban' in str(value_str).lower()
            elif "Rural" in label: is_yes = 'rural' in str(value_str).lower()
            else: is_yes = 'yes' in str(value_str).lower()
            
            css = "status-yes" if is_yes else "status-no"
            val_css = "val-yes" if is_yes else "val-no"
            txt = "YES" if is_yes else "NO"
            return f"<div class='indicator-box {css}'><div class='indicator-label'>{label}</div><div class='indicator-value {val_css}'>{txt}</div></div>"

        # 2x2 Indicators
        i_l, i_r = st.columns(2)
        m_val = row.get('Rural or Urban', '')
        with i_l:
            st.markdown(get_ind_html("Metro (Urban)", m_val), unsafe_allow_html=True)
            st.markdown(get_ind_html("Rural", m_val), unsafe_allow_html=True)
        with i_r:
            st.markdown(get_ind_html("NMTC Eligible", row.get('NMTC Eligible', '')), unsafe_allow_html=True)
            st.markdown(get_ind_html("NMTC Deeply Distressed", row.get('NMTC Distressed', '')), unsafe_allow_html=True)

        # 8 Demographic Cards
        m_cols = st.columns(4)
        m_cols[0].metric("Median Home", safe_num(row.get(M_MAP["home"]), True))
        m_cols[1].metric("Disability", safe_num(row.get(M_MAP["dis"])))
        m_cols[2].metric("Age 65+", safe_num(row.get(M_MAP["pop65"])))
        m_cols[3].metric("Labor Force", safe_num(row.get(M_MAP["labor"])))
        
        m_cols = st.columns(4)
        m_cols[0].metric("Unemployed", safe_num(row.get(M_MAP["unemp"])))
        m_cols[1].metric("HS Grad+", safe_num(row.get(M_MAP["hs"])))
        m_cols[2].metric("Bachelor's+", safe_num(row.get(M_MAP["bach"])))
        m_cols[3].metric("Broadband", safe_num(row.get(M_MAP["web"])))

        # Anchor Table
        st.markdown("<p style='font-size:0.8rem; font-weight:bold; margin-top:15px; color:#ffffff;'>NEAREST ANCHOR ASSETS</p>", unsafe_allow_html=True)
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_dist = anchor_df.copy()
            a_dist['d'] = a_dist.apply(lambda x: calculate_distance(t_pos['lat'], t_pos['lon'], x['lat'], x['lon']), axis=1)
            top5 = a_dist.sort_values('d').head(5)
            table_html = "<table class='anchor-table'><tr><th>DIST</th><th>NAME</th><th>TYPE</th></tr>"
            for _, a in top5.iterrows():
                table_html += f"<tr><td>{a['d']:.1f} mi</td><td>{a['name'].upper()}</td><td>{