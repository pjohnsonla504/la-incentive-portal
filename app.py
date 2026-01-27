import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="OZ 2.0 Recommendation Portal", layout="wide")

# Establish connection using the secrets provided
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Configuration Error: {e}")
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
            u_input = st.text_input("Username").strip()
            p_input = st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                try:
                    # Read fresh user data from the 'Users' tab
                    user_db = conn.read(worksheet="Users", ttl=0)
                    user_db.columns = [str(c).strip() for c in user_db.columns]
                    
                    # Robust matching (stripping spaces from the sheet data as well)
                    user_db['Username'] = user_db['Username'].astype(str).str.strip()
                    user_db['Password'] = user_db['Password'].astype(str).str.strip()
                    
                    match = user_db[(user_db['Username'] == u_input) & (user_db['Password'] == p_input)]
                    
                    if not match.empty:
                        user_data = match.iloc[0]
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = u_input
                        st.session_state["role"] = str(user_data['Role']).strip()
                        st.session_state["a_type"] = str(user_data['Assigned_Type']).strip()
                        st.session_state["a_val"] = str(user_data['Assigned_Value']).strip()
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")
                except Exception as e:
                    st.error(f"Connection Error (400): {e}")
                    st.info("💡 Ensure your Google Sheet tab is named 'Users' and shared with the service account email.")
    st.stop()

# --- 3. DATA LOADING (Local Repo Files) ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    
    # Standardize GEOID
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # Clean Numeric Columns
    cols_to_fix = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus']
    for col in cols_to_fix:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # Static Designation Logic
    state_median = master['med_hh_income'].median()
    urban_parishes = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urban_parishes)) & (master['pop_total'] < 5000), 1, 0)
    master['nmtc_eligible'] = np.where((master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (state_median * 0.8)), 1, 0)
    
    is_severe = (master['poverty_rate'] >= 30) | (master['med_hh_income'] <= (state_median * 0.6)) | (master['unemp_rate'] >= 9.0)
    master['deep_distress'] = np.where((master['poverty_rate'] >= 40) | (master['med_hh_income'] <= (state_median * 0.4)) | (master['unemp_rate'] >= 15.0) | ((master['is_rural'] == 1) & is_severe), 1, 0)

    # Load GeoJSON from repo
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# Filter tracts based on User's Assignment
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- 4. SHEET1 DATA (Recommendations & Quota) ---
try:
    existing_recs = conn.read(worksheet="Sheet1", ttl=0)
    # Highlight rule: Green = Eligible for OZ 2.0
    eligible_in_view = master_df[master_df['Is_Eligible'] == 1]
    quota_limit = max(1, int(len(eligible_in_view) * 0.25))
    current_usage = len(existing_recs[existing_recs['User'] == st.session_state["username"]])
    quota_remaining = quota_limit - current_usage
except Exception:
    existing_recs = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification", "Document"])
    quota_limit, current_usage, quota_remaining = 1, 0, 1

# --- 5. INTERFACE ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")

# Progress Bar
q_col1, q_col2 = st.columns([0.7, 0.3])
prog_val = min(1.0, current_usage / quota_limit) if quota_limit > 0 else 0
q_col1.progress(prog_val)
q_col2.write(f"**Usage:** {current_usage} / {quota_limit} Recommendations")

col_map, col_metrics = st.columns([0.6, 0.4])

with col_map:
    f1, f2 = st.columns(2)
    with f1:
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Filter Parish", options=p_list, label_visibility="collapsed")
    with f2:
        only_elig = st.toggle("Show Eligible Only (Green)")

    map_df = master_df.copy()
    if sel_parish != "All Authorized Parishes":
        map_df = map_df[map_df['Parish'] == sel_parish]
    
    if only_elig:
        map_df = map_df[map_df['Is_Eligible'] == 1]

    # Map Config (Grey for Ineligible, Green for OZ 2.0 Eligible)
    fig = px.choropleth_mapbox(
        map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )
    fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')
    
    selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
        st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

with col_metrics:
    has_sel = st.session_state["selected_tract"] is not None
    disp = master_df[master_df['GEOID'] ==