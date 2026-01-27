import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
import io
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

# --- 1. SETUP ---
st.set_page_config(page_title="OZ 2.0 Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

SPREADSHEET_ID = "1qXFpZjiq8-G9U_D_u0k301Vocjlzki-6uDZ5UfOO8zM"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
FOLDER_ID = "1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk"

def get_drive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.file"])
    return build('drive', 'v3', credentials=creds)

if "authenticated" not in st.session_state: st.session_state["authenticated"] = False

# --- 2. AUTH ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            try:
                # Defaulting to the FIRST tab (Users) to avoid range errors
                db = conn.read(spreadsheet=SHEET_URL, ttl=0)
                db.columns = [str(c).strip() for c in db.columns]
                m = db[(db['Username'] == u) & (db['Password'] == p)]
                
                if not m.empty:
                    st.session_state.update({
                        "authenticated": True, 
                        "username": u, 
                        "role": str(m.iloc[0]['Role']), 
                        "a_type": str(m.iloc[0]['Assigned_Type']), 
                        "a_val": str(m.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else: st.error("Invalid Username or Password.")
            except Exception as e: 
                st.error(f"Connection Error: {e}")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("tract_data_final.csv")
    df.columns = [str(c).strip() for c in df.columns]
    df['GEOID'] = df['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    for c in ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']:
        df[c] = pd.to_numeric(df[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    return df, gj

master_df, la_geojson = load_data()
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

try:
    # Explicitly call Sheet1 for recs
    recs = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)
    lim = max(1, int(len(master_df[master_df['Is_Eligible'] == 1]) * 0.25))
    used = len(recs[recs['User'] == st.session_state["username"]])
except:
    recs, lim, used = pd.DataFrame(), 0, 0

# --- 4. UI ---
st.title(f"📍 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, used / lim) if lim > 0 else 0)

c_map, c_met = st.columns([0.6, 0.4])
with c_map:
    p_opt = ["All"] + sorted(master_df['Parish'].unique().tolist())
    p_sel = st.selectbox("Parish", p_opt)
    only_e = st.toggle("Show OZ 2.0 Eligible Only (Green)")
    m_df = master_df.copy()
    if p_sel != "All": m_df = m_df[m_df['Parish'] == p_sel]
    if only_e: m_df = m_df[m_df['Is_Eligible'] == 1]
    fig = px.choropleth_mapbox(m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID", color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")], mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8}, opacity=0.6)
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    st.plotly_chart(fig, use_container_width=True)

with c_met:
    st.info("Select a tract on the map to begin.")