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

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="OZ 2.0 Portal", layout="wide")

# Ensure these match your actual Google assets
SPREADSHEET_ID = "1qXFpZjiq8-G9U_D_u0k301Vocjlzki-6uDZ5UfOO8zM"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"
FOLDER_ID = "1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk"

conn = st.connection("gsheets", type=GSheetsConnection)

def get_drive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build('drive', 'v3', credentials=creds)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

# --- 2. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Access Portal"):
            try:
                # We use the full URL and worksheet name. 
                # Ensure the tab is named exactly 'Users'
                user_db = conn.read(spreadsheet=SHEET_URL, worksheet="Users", ttl=0)
                user_db.columns = [str(c).strip() for c in user_db.columns]
                
                match = user_db[(user_db['Username'] == u) & (user_db['Password'] == p)]
                
                if not match.empty:
                    user_data = match.iloc[0]
                    st.session_state.update({
                        "authenticated": True,
                        "username": u,
                        "role": str(user_data['Role']).strip(),
                        "a_type": str(user_data['Assigned_Type']).strip(),
                        "a_val": str(user_data['Assigned_Value']).strip()
                    })
                    st.rerun()
                else:
                    st.error("Invalid Username or Password.")
            except Exception as e:
                st.error(f"Login connection error: {e}")
                st.info("Check: 1. Tab named 'Users'? 2. Service Account shared as 'Editor'?")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    cols_to_fix = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']
    for col in cols_to_fix:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    state_median = master['med_hh_income'].median()
    urban_parishes = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urban_parishes)) & (master['pop_total'] < 5000), 1, 0)
    master['nmtc_eligible'] = np.where((master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (state_median * 0.8)), 1, 0)
    
    is_severe = (master['poverty_rate'] >= 30) | (master['med_hh_income'] <= (state_median * 0.6)) | (master['unemp_rate'] >= 9.0)
    master['deep_distress'] = np.where((master['poverty_rate'] >= 40) | (master['med_hh_income'] <= (state_median * 0.4)) | (master['unemp_rate'] >= 15.0) | ((master['is_rural'] == 1) & is_severe), 1, 0)

    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# User Filter
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# History/Quota Load
try:
    existing_recs = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)
    eligible_count = len(master_df[master_df['Is_Eligible'] == 1])
    quota_limit = max(1, int(eligible_count * 0.25))
    current_usage = len(existing_recs[existing_recs['User'] == st.session_state["username"]])
except:
    existing_recs, quota_limit, current_usage = pd.DataFrame(), 0, 0

# --- 4. DASHBOARD UI ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, current_usage / quota_limit) if quota_limit > 0 else 0)
st.write(f"**Recommendations:** {current_usage} / {quota_limit}")

col_map, col_metrics = st.columns([0.6, 0.4])

with col_map:
    p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
    sel_parish = st.selectbox("Filter Parish", options=p_list)
    only_elig = st.toggle("OZ 2.0 Eligible Only (Green)")

    m_df = master_df.copy()
    if sel_parish != "All Authorized Parishes":
        m_df = m_df[m_df['Parish'] == sel_parish]
    
    if only_elig:
        m_df = m_df[m_df['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    
    map_sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if map_sel and "selection" in map_sel and len(map_sel["selection"]["points"]) > 0:
        st.session_state["selected_tract"] = map_sel["selection"]["points"][0]["location"]

with col_metrics:
    has_sel = st.session_state["selected_tract"] is not None
    disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0] if has_sel else master_df.iloc[0]
    
    st.subheader(f"📊 Tract {st.session_state['selected_tract'][-4:] if has_sel else 'Profile'}")
    
    m1, m2 = st.columns(2)
    m1.metric("Median Income", f"${disp['med_hh_income']:,.0f}")
    m2.metric("Poverty Rate", f"{disp['poverty_rate']:.1f}%")
    
    st.markdown("---")
    if has_sel:
        with st.form("rec_form"):
            cat = st.selectbox("Category", ["Housing", "Healthcare", "Infrastructure", "Commercial", "Other"])
            txt = st.text_area("Justification")
            up_pdf = st.file_uploader("Upload PDF", type="pdf")
            if st.form_submit_button("Submit"):
                try:
                    lnk = "None"
                    if up_pdf:
                        svc = get_drive_service()
                        meta = {'name': f"REC_{disp['GEOID']}", 'parents': [FOLDER_ID]}
                        media = MediaIoBaseUpload(io.BytesIO(up_pdf.getvalue()), mimetype='application/pdf')
                        f_meta = svc.files().create(body=meta, media_body=media, fields='id').execute()
                        lnk = f"https://drive.google.com/file/d/{f_meta.get('id')}/view"

                    new_row = pd.DataFrame([{
                        "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                        "GEOID": disp['GEOID'],
                        "Category": cat,
                        "Justification": txt,
                        "Is_Eligible": int(disp['Is_Eligible']),
                        "User": st.session_state["username"],
                        "Document": lnk
                    }])
                    conn.create(spreadsheet=SHEET_URL, worksheet="Sheet1", data=new_row)
                    st.success("Submitted!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    else:
        st.info("Select a tract on the map to begin.")

# --- 5. HISTORY ---
st.markdown("---")
st.subheader("📋 My Submission History")
if not existing_recs.empty:
    u_recs = existing_recs[existing_recs['User'] == st.session_state["username"]]
    st.dataframe(u_recs, use_container_width=True, hide_index=True)