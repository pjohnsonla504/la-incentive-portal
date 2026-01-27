import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="OZ 2.0 Portal", layout="wide")

# Establish connection
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Config Error: {e}")
    st.stop()

# Initialize Session States
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

# --- 2. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Recommendation Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in = st.text_input("Username").strip()
            p_in = st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                try:
                    user_db = conn.read(worksheet="Users", ttl=0)
                    user_db.columns = [str(c).strip() for c in user_db.columns]
                    user_db['Username'] = user_db['Username'].astype(str).str.strip()
                    user_db['Password'] = user_db['Password'].astype(str).str.strip()
                    match = user_db[(user_db['Username'] == u_in) & (user_db['Password'] == p_in)]
                    if not match.empty:
                        st.session_state.update({
                            "authenticated": True, 
                            "username": u_in, 
                            "role": str(match.iloc[0]['Role']).strip(), 
                            "a_type": str(match.iloc[0]['Assigned_Type']).strip(), 
                            "a_val": str(match.iloc[0]['Assigned_Value']).strip()
                        })
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                except Exception as e:
                    st.error(f"Login Error: {e}")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # Cleaning the 7 indicators + population
    num_cols = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus']
    for c in num_cols:
        if c in master.columns:
            master[c] = pd.to_numeric(master[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    s_med = master['med_hh_income'].median()
    urb_p = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urb_p)) & (master['pop_total'] < 5000), 1, 0)
    master['nmtc_eligible'] = np.where((master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (s_med * 0.8)), 1, 0)
    sev = (master['poverty_rate'] >= 30) | (master['med_hh_income'] <= (s_med * 0.6)) | (master['unemp_rate'] >= 9.0)
    master['deep_distress'] = np.where((master['poverty_rate'] >= 40) | (master['med_hh_income'] <= (s_med * 0.4)) | (master['unemp_rate'] >= 15.0) | ((master['is_rural'] == 1) & sev), 1, 0)

    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- 4. RECOMMENDATIONS ---
try:
    existing_recs = conn.read(worksheet="Sheet1", ttl=0)
    elig_count = len(master_df[master_df['Is_Eligible'] == 1])
    quota_limit = max(1, int(elig_count * 0.25))
    curr_use = len(existing_recs[existing_recs['User'] == st.session_state["username"]])
    q_rem = quota_limit - curr_use
except:
    existing_recs, quota_limit, curr_use, q_rem = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification", "Document"]), 1, 0, 1

# --- 5. MAIN UI ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
q_col1, q_col2 = st.columns([0.7, 0.3])
q_col1.progress(min(1.0, curr_use / quota_limit) if quota_limit > 0 else 0)
q_col2.write(f"**Recommendations:** {curr_use} / {quota_limit}")

c_map, c_