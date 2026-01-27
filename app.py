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

# Config
DEFAULT_URL = "https://docs.google.com/spreadsheets/d/1qXFpZjiq8-G9U_D_u0k301Vocjlzki-6uDZ5UfOO8zM/edit"
SHEET_URL = st.secrets.get("public_gsheets_url", DEFAULT_URL)
FOLDER_ID = "1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk"

def get_drive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(info, scopes=["https://www.googleapis.com/auth/drive.file"])
    return build('drive', 'v3', credentials=creds)

for key in ["authenticated", "selected_tract"]:
    if key not in st.session_state: st.session_state[key] = False if key=="authenticated" else None

# --- 2. AUTH ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login_form"):
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Login"):
            try:
                db = conn.read(spreadsheet=SHEET_URL, worksheet="Users", ttl=0)
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
                else: st.error("Invalid Login")
            except Exception as e: st.error(f"Error: {e}")
    st.stop()

# --- 3. DATA ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("tract_data_final.csv")
    df.columns = [str(c).strip() for c in df.columns]
    df['GEOID'] = df['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    for c in ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']:
        df[c] = pd.to_numeric(df[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    sm = df['med_hh_income'].median()
    urb = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    df['is_rural'] = np.where((~df['Parish'].isin(urb)) & (df['pop_total'] < 5000), 1, 0)
    df['nmtc_eligible'] = np.where((df['poverty_rate'] >= 20) | (df['med_hh_income'] <= (sm * 0.8)), 1, 0)
    
    sev = (df['poverty_rate'] >= 30) | (df['med_hh_income'] <= (sm * 0.6)) | (df['unemp_rate'] >= 9.0)
    df['deep_distress'] = np.where((df['poverty_rate'] >= 40) | (df['med_hh_income'] <= (sm * 0.4)) | (df['unemp_rate'] >= 15.0) | ((df['is_rural'] == 1) & sev), 1, 0)

    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    return df, gj

master_df, la_geojson = load_data()
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

try:
    recs = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)
    # Highlighted tracts are those eligible for Opportunity Zone 2.0
    lim = max(1, int(len(master_df[master_df['Is_Eligible'] == 1]) * 0.25))
    used = len(recs[recs['User'] == st.session_state["username"]])
except:
    recs, lim, used = pd.DataFrame(), 0, 0

# --- 4. UI ---
st.title(f"📍 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, used / lim) if lim > 0 else 0)
st.write(f"Usage: {used}/{lim}")

c_map, c_met = st.columns([0.6, 0.4])
with c_map:
    p_opt = ["All"] + sorted(master_df['Parish'].unique().tolist())
    p_sel = st.selectbox("Parish", p_opt)
    only_e = st.toggle("OZ 2.0 Eligible Only")
    
    m_df = master_df.copy()
    if p_sel != "All": m_df = m_df[m_df['Parish'] == p_sel]
    if only_e: m_df = m_df[m_df['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID", color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")], mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8}, opacity=0.6)
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if sel and "selection" in sel and len(sel["selection"]["points"]) > 0:
        st.session_state["selected_tract"] = sel["selection"]["points"][0]["location"]

with c_met:
    has = st.session_state["selected_tract"] is not None
    d = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0] if has else master_df.iloc[0]
    st.subheader(f"Tract {st.session_state['selected_tract'][-4:] if has else 'Select'}")
    
    st.metric("Income", f"${d['med_hh_income']:,.0f}")
    st.metric("Poverty", f"{d['poverty_rate']:.1f}%")
    
    if st.session_state["selected_tract"]:
        with st.form("sub"):
            cat = st.selectbox("Type", ["Housing", "Infrastructure", "Commercial"])
            txt = st.text_area("Justification")
            pdf = st.file_uploader("PDF", type="pdf")
            if st.form_submit_button("Submit"):
                try:
                    lnk = "None"
                    if pdf:
                        svc = get_drive_service()
                        meta = {'name': f"REC_{d['GEOID']}_{pdf.name}", 'parents': [FOLDER_ID]}
                        media = MediaIoBaseUpload(io.BytesIO(pdf.getvalue()), mimetype='application/pdf')
                        df_id = svc.files().create(body=meta, media_body=media, fields='id').execute()
                        lnk = f"https://drive.google.com/file/d/{df_id.get('id')}/view"
                    
                    # Exact header match: Date, GEOID, Category, Justification, Is_Eligible, User, Document
                    new = pd.DataFrame([{
                        "Date": pd.Timestamp.now().strftime("%Y-%m-%d"), 
                        "GEOID": d['GEOID'], 
                        "Category": cat, 
                        "Justification": txt, 
                        "Is_Eligible": int(d['Is_Eligible']),
                        "User": st.session_state["username"], 
                        "Document": lnk
                    }])
                    conn.create(spreadsheet=SHEET_URL, worksheet="Sheet1", data=new)
                    st.success("Saved!")
                    st.rerun()
                except Exception as e: st.error(f"Save failed: {e}")

st.divider()
st.subheader("My Submissions")
if not recs.empty:
    st.dataframe(recs[recs['User'] == st.session_state["username"]], use_container_width=True)