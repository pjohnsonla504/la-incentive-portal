import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection
import streamlit.components.v1 as components

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Initialize session state keys
if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- HELPERS ---
def safe_float(val):
    try:
        if pd.isna(val) or val == '' or val == 'N/A': return 0.0
        s = str(val).replace('$', '').replace(',', '').replace('%', '').strip()
        return float(s)
    except: return 0.0

def safe_int(val):
    return int(safe_float(val))

# --- 1. PERSISTENCE ENGINE ---
def load_user_recs(username):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        recs_df = conn.read(worksheet="Recommendations", ttl=0) 
        if recs_df.empty:
            return []
        user_recs = recs_df[recs_df['username'] == username].to_dict('records')
        return user_recs
    except Exception as e:
        return []

def save_rec_to_cloud(rec_entry):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        existing_df = conn.read(worksheet="Recommendations", ttl=0)
        rec_entry['username'] = st.session_state["username"]
        new_row_df = pd.DataFrame([rec_entry])
        if not existing_df.empty:
            updated_df = pd.concat([existing_df, new_row_df], ignore_index=True)
        else:
            updated_df = new_row_df
        conn.update(worksheet="Recommendations", data=updated_df)
    except Exception as e:
        st.error(f"Cloud Save Failed: {e}")

# --- 2. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username_input"].strip()
            p = str(st.session_state["password_input"]).strip()
            
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = u
                    st.session_state["session_recs"] = load_user_recs(u)
                    return
            st.session_state["password_correct"] = False
            st.error("Invalid username or password")
        except Exception as e:
            st.error(f"Error connecting to database: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""
            <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
            .stApp { background-color: #0b0f19 !important; font-family: 'Inter', sans-serif; }
            div[data-testid="stVerticalBlock"] > div:has(input) {
                background-color: #111827; padding: 40px; border-radius: 15px;
                border: 1px solid #1e293b; box-shadow: 0 10px 25px rgba(0,0,0,0.3);
            }
            label { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.05em; }
            input { background-color: #0b0f19 !important; color: white !important; border: 1px solid #2d3748 !important; border-radius: 8px !important; }
            button[kind="primary"], .stButton > button { background-color: #4ade80 !important; color: #0b0f19 !important; font-weight: 900 !important; border: none !important; height: 3em !important; margin-top: 10px; }
            button:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(74, 222, 128, 0.3); }
            .login-header { text-align: center; margin-bottom: 2rem; }
            </style>
        """, unsafe_allow_html=True)

        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("""
                <div class="login-header">
                    <p style='color: #4ade80; font-weight: 900; letter-spacing: 0.2em; font-size: 0.8rem; margin-bottom: 0;'>SECURE ACCESS</p>
                    <h1 style='color: white; font-weight: 900; margin-top: 0;'>OZ 2.0 Portal</h1>
                </div>
            """, unsafe_allow_html=True)
            with st.container():
                st.text_input("Username", key="username_input", placeholder="Enter your username")
                st.text_input("Password", type="password", key="password_input", placeholder="••••••••")
                st.button("Sign In", on_click=password_entered, use_container_width=True)
            st.markdown("<p style='text-align:center; color:#475569; font-size:0.8rem; margin-top:20px;'>Louisiana Opportunity Zones 2.0 | Admin Access Only</p>", unsafe_allow_html=True)
        return False
    return True

if check_password():
    # --- 3. GLOBAL STYLING & FROZEN NAV ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; scroll-behavior: smooth; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background-color: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px 50px; z-index: 999999; display: flex; justify-content: center; gap: 30px; backdrop-filter: blur(10px); }
        .nav-link, .nav-link:link, .nav-link:visited { color: #ffffff !important; text-decoration: none !important; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.1em; transition: color 0.3s ease; }
        .nav-link:hover, .nav-link:active { color: #4ade80 !important; text-decoration: none !important; }
        .main .block-container { padding-top: 80px !important; }
        div[data-baseweb="select"] > div { background-color: #ffffff !important; border: 1px solid #cbd5e1 !important; border-radius: 6px !important; }
        div[data-baseweb="select"] * { color: #0f172a !important; }
        label[data-testid="stWidgetLabel"] { color: #94a3b8 !important; font-weight: 700 !important; text-transform: uppercase; font-size: 0.75rem !important; letter-spacing: 0.05em; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 10px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-size: 3.8rem; font-weight: 900; color: #f8fafc; margin-bottom: 20px; line-height: 1.1; }
        .narrative-text { font-size: 1.15rem; color: #94a3b8; line-height: 1.7; max-width: 900px; margin-bottom: 30px; }
        .benefit-card { background-color: #111827 !important; padding: 30px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; min-height: 280px; transition: all 0.3s ease; display: flex; flex-direction: column; }
        .benefit-card:hover { border-color: #4ade80 !important; transform: translateY(-5px); }
        .benefit-card h3 { color: #f8fafc; margin-bottom: 15px; font-weight: 800; font-size: 1.3rem; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; flex-grow: 1; }
        .benefit-card a { color: #4ade80; text-decoration: none; font-weight: 700; margin-top: 15px; }
        .metric-card { background-color: #111827 !important; padding: 10px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 95px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 10px; }
        .metric-value { font-size: 1.05rem; font-weight: 900; color: #4ade80; line-height: 1.1; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; margin-top: 4px; letter-spacing: 0.05em; }
        .anchor-card { background:#111827; border:1px solid #1e293b; padding:15px; border-radius:10px; margin-bottom:12px; }
        </style>

        <div class="nav-container">
            <a class="nav-link" href="#section-1">Overview</a>
            <a class="nav-link" href="#section-2">Benefits</a>
            <a class="nav-link" href="#section-3">Strategy</a>
            <a class="nav-link" href="#section-4">Best Practices</a>
            <a class="nav-link" href="#section-5">Mapping</a>
        </div>
        """, unsafe_allow_html=True)

    # --- 4. DATA ENGINE ---
    @st.cache_data(ttl=3600)
    def load_assets():
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        def read_csv_with_fallback(path):
            for enc in ['utf-8', 'latin1', 'cp1252']:
                try: return pd.read_csv(path, encoding=enc)
                except: continue
            return pd.read_csv(path)

        master = read_csv_with_fallback("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1', 'true'] else 'Ineligible'
        )
        anchors = read_csv_with_fallback("la_anchors.csv")
        anchors['Type'] = anchors['Type'].fillna('Other')
        return gj, master, anchors

    gj, master_df, anchors_df = load_assets()

    def get_zoom_center(geoids):
        if not geoids or not gj: return {"lat": 30.9, "lon": -91.8}, 6.0
        # Zoom logic simplified for brevity
        return {"lat": 30.9, "lon": -91.8}, 6.5

    def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        
        # --- FEATURE: IDENTIFY SELECTED TRACTS ---
        # Convert all Tract IDs in session state to strings for accurate matching
        selected_geoids = [str(rec['Tract']) for rec in st.session_state["session_recs"]]
        
        def get_color_cat(row):
            # Category 2 = Orange (In Report)
            if str(row['geoid_str']) in selected_geoids: return 2
            # Category 1 = Green (Eligible), Category 0 = Grey (Ineligible)
            return 1 if row['Eligibility_Status'] == 'Eligible' else 0
        
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        
        focus_geoids = {st.session_state["active_tract"]} if st.session_state.get("active_tract") else set(map_df['geoid_str'].tolist())
        center, zoom = get_zoom_center(focus_geoids)
        
        fig = go.Figure()
        fig.add_trace(go.Choroplethmapbox(
            geojson=gj, 
            locations=map_df['geoid_str'], 
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            # SCALE: [Grey, Green, Orange]
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], 
            zmin=0, zmax=2,
            showscale=False, 
            marker=dict(opacity=0.6, line=dict(width=1.2, color='black')),
            hoverinfo="location",
            name="Census Tracts"
        ))

        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, height=700, 
            uirevision="constant"
        )
        return fig

    # --- MAPPING SECTION ---
    st.markdown("<div id='section-5'></div>", unsafe_allow_html=True)
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Mapping</div></div>", unsafe_allow_html=True)
    
    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1: selected_region = st.selectbox("Region", ["All Louisiana"] + sorted(master_df['Region'].dropna().unique().tolist()))
    filtered_df = master_df.copy()
    if selected_region != "All Louisiana": filtered_df = filtered_df[filtered_df['Region'] == selected_region]
    
    with f_col2: selected_parish = st.selectbox("Parish", ["All in Region"] + sorted(filtered_df['Parish'].dropna().unique().tolist()))
    if selected_parish != "All in Region": filtered_df = filtered_df[filtered_df['Parish'] == selected_parish]
    
    with f_col3:
        tract_list = ["Search Tract GEOID..."] + sorted([str(x) for x in filtered_df['geoid_str'].tolist()])
        selected_search = st.selectbox("Find Census Tract", tract_list)
        if selected_search != "Search Tract GEOID...":
            st.session_state["active_tract"] = selected_search

    st.plotly_chart(render_map_go(filtered_df), use_container_width=True)

    if st.session_state["active_tract"]:
        curr = st.session_state["active_tract"]
        row = master_df[master_df["geoid_str"] == str(curr)].iloc[0]
        
        st.markdown(f"### Tract {curr} Details")
        rec_cat = st.selectbox("Category", ["Housing", "Business", "Tech", "Healthcare"])
        justification = st.text_area("Justification")
        
        if st.button("Add to Recommendation Report", type="primary"):
            new_entry = {
                "Tract": curr, 
                "Parish": row['Parish'],
                "Category": rec_cat, 
                "Justification": justification
            }
            save_rec_to_cloud(new_entry)
            # Refresh local session state
            st.session_state["session_recs"] = load_user_recs(st.session_state["username"])
            st.toast(f"Tract {curr} Highlighted Orange!")
            st.rerun()