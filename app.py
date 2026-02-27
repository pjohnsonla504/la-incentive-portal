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

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

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

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username"].strip()
            p = str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
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
                st.text_input("Username", key="username")
                st.text_input("Password", type="password", key="password")
                st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 2. STYLING & NAVIGATION ---
    st.markdown("""
        <style>
        html, body, [class*="stApp"] { background-color: #0b0f19 !important; color: #ffffff; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background: rgba(11, 15, 25, 0.98); border-bottom: 1px solid #1e293b; padding: 15px; z-index: 999; display: flex; justify-content: center; gap: 30px; }
        .nav-link { color: #ffffff !important; text-decoration: none; font-weight: 700; font-size: 0.75rem; text-transform: uppercase; }
        .nav-link:hover { color: #4ade80 !important; }
        .main .block-container { padding-top: 80px !important; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.2rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; color: #94a3b8; text-transform: uppercase; }
        </style>
        <div class="nav-container">
            <a class="nav-link" href="#section-1">Strategic Overview</a>
            <a class="nav-link" href="#section-5">Mapping Engine</a>
            <a class="nav-link" href="#section-6">Investment Report</a>
        </div>
    """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    @st.cache_data(ttl=3600)
    def load_assets():
        # Load GeoJSON
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        # Load Master Data
        master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv", encoding='latin1')
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
        # Map Eligibility (Strict Rule: Green ONLY if Eligible)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )

        # Load Anchors
        anchors = pd.read_csv("la_anchors.csv", encoding='latin1')
        
        return gj, master, anchors

    gj, master_df, anchors_df = load_assets()

    # --- 4. MAPPING FUNCTION ---
    def render_map(df):
        map_df = df.copy()
        
        # Color Logic: 1 for Eligible (Green), 0 for Ineligible (Grey)
        map_df['Color_Val'] = map_df['Eligibility_Status'].map({'Eligible': 1, 'Ineligible': 0})
        
        fig = go.Figure()

        # Census Tract Layer
        fig.add_trace(go.Choroplethmapbox(
            geojson=gj,
            locations=map_df['geoid_str'],
            z=map_df['Color_Val'],
            featureidkey="properties.GEOID",
            colorscale=[[0, '#334155'], [1, '#4ade80']], # Grey to Neon Green
            showscale=False,
            marker=dict(opacity=0.6, line=dict(width=0.5, color='white')),
            name="Census Tracts"
        ))

        # Anchor Assets Layer (Grouped by Type)
        anchor_types = anchors_df['Type'].unique()
        colors = px.colors.qualitative.Bold
        
        for i, a_type in enumerate(anchor_types):
            t_data = anchors_df[anchors_df['Type'] == a_type]
            fig.add_trace(go.Scattermapbox(
                lat=t_data['Lat'], lon=t_data['Lon'],
                mode='markers',
                marker=go.scattermapbox.Marker(size=10, color=colors[i % len(colors)]),
                text=t_data['Name'],
                name=str(a_type),
                visible="legendonly"
            ))

        fig.update_layout(
            mapbox=dict(style="carto-darkmatter", zoom=6, center={"lat": 30.9, "lon": -91.8}),
            margin={"r":0,"t":0,"l":0,"b":0},
            height=700,
            legend=dict(bgcolor="rgba(11, 15, 25, 0.8)", font=dict(color="white"))
        )
        return fig

    # --- 5. UI LAYOUT ---
    st.markdown("<div id='section-1'></div>", unsafe_allow_html=True)
    st.title("Louisiana Opportunity Zones 2.0")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown('<div class="metric-card"><div class="metric-value">150+</div><div class="metric-label">Eligible Tracts</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="metric-card"><div class="metric-value">Active</div><div class="metric-label">OZ 2.0 Status</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown('<div class="metric-card"><div class="metric-value">8</div><div class="metric-label">Anchor Categories</div></div>', unsafe_allow_html=True)

    st.markdown("<div id='section-5' style='margin-top:50px;'></div>", unsafe_allow_html=True)
    st.subheader("Interactive Opportunity Map")
    
    # Filter by Parish
    parish_list = sorted(master_df['Parish'].dropna().unique())
    sel_parish = st.selectbox("Filter by Parish", ["All Louisiana"] + parish_list)
    
    filtered_df = master_df if sel_parish == "All Louisiana" else master_df[master_df['Parish'] == sel_parish]
    
    st.plotly_chart(render_map(filtered_df), use_container_width=True)

    # --- DATA TABLE ---
    st.markdown("<div id='section-6' style='margin-top:50px;'></div>", unsafe_allow_html=True)
    st.subheader("Tract Eligibility & Metrics")
    
    # Display table showing only specific columns for clarity
    display_cols = ['geoid_str', 'Parish', 'Eligibility_Status', 'Median Household Income', 'Poverty Rate']
    st.dataframe(
        filtered_df[display_cols].style.applymap(
            lambda x: 'color: #4ade80; font-weight: bold;' if x == 'Eligible' else '', 
            subset=['Eligibility_Status']
        ),
        use_container_width=True
    )

    st.write("---")
    st.caption("Louisiana Opportunity Zones 2.0 Portal | Data sourced from Opportunity Zones Master File and LA Anchors CSV.")

# Would you like me to add a specific 'Download CSV' button for the filtered results in the Report section?