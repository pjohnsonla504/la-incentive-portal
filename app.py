import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# --- 1. SETUP & CONFIG ---
st.set_page_config(page_title="OZ 2.0 Recommendation Portal", layout="wide")

# Master URL for Google Sheets
SPREADSHEET_ID = "1qXFpZjiq8-G9U_D_u0k301Vocjlzki-6uDZ5UfOO8zM"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit"

conn = st.connection("gsheets", type=GSheetsConnection)

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
                # Read Users tab directly using the URL
                user_db = conn.read(spreadsheet=SHEET_URL, worksheet="Users", ttl=0)
                user_db.dropna(how='all', inplace=True)
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
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Load local CSV
    df = pd.read_csv("tract_data_final.csv")
    df.columns = [str(c).strip() for c in df.columns]
    
    # Format GEOIDs
    if 'GEOID' in df.columns:
        df['GEOID'] = df['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # Numeric cleanup
    for c in ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # Logic for NMTC and Deep Distress
    sm = df['med_hh_income'].median()
    urb = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    df['is_rural'] = np.where((~df['Parish'].isin(urb)) & (df['pop_total'] < 5000), 1, 0)
    df['nmtc_eligible'] = np.where((df['poverty_rate'] >= 20) | (df['med_hh_income'] <= (sm * 0.8)), 1, 0)
    
    sev = (df['poverty_rate'] >= 30) | (df['med_hh_income'] <= (sm * 0.6)) | (df['unemp_rate'] >= 9.0)
    df['deep_distress'] = np.where((df['poverty_rate'] >= 40) | (df['med_hh_income'] <= (sm * 0.4)) | (df['unemp_rate'] >= 15.0) | ((df['is_rural'] == 1) & sev), 1, 0)

    # Load local GeoJSON
    with open("tl_2025_22_tract.json") as f:
        gj = json.load(f)
    return df, gj

master_df, la_geojson = load_data()

# User Assignment Filtering
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Fetch recommendation history and calculate Quotas
try:
    recs = conn.read(spreadsheet=SHEET_URL, worksheet="Sheet1", ttl=0)
    recs.dropna(how='all', inplace=True)
    eligible_count = len(master_df[master_df['Is_Eligible'] == 1])
    quota_limit = max(1, int(eligible_count * 0.25))
    current_usage = len(recs[recs['User'] == st.session_state["username"]])
    quota_remaining = quota_limit - current_usage
except:
    recs, quota_limit, current_usage, quota_remaining = pd.DataFrame(), 0, 0, 0

# --- 4. DASHBOARD UI ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")

# Quota Progress Bar
q_col1, q_col2 = st.columns([0.7, 0.3])
q_col1.progress(min(1.0, current_usage / quota_limit) if quota_limit > 0 else 0)
q_col2.write(f"**Recommendations:** {current_usage} / {quota_limit}")

col_map, col_metrics = st.columns([0.6, 0.4])

with col_map:
    f1, f2 = st.columns(2)
    with f1:
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Isolate Parish", options=p_list, label_visibility="collapsed")
    with f2:
        only_elig = st.toggle("OZ 2.0 Eligible Only (Green)")

    map_df = master_df.copy()
    if sel_parish != "All Authorized Parishes":
        map_df = map_df[map_df['Parish'] == sel_parish]
    
    # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0
    if only_elig:
        map_df = map_df[map_df['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(
        map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    
    selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
        st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

with col_metrics:
    has_sel = st.session_state["selected_tract"] is not None
    # Profile display (default to first row if nothing selected)
    disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0] if has_sel else master_df.iloc[0]
    
    st.subheader(f"📊 Tract {st.session_state['selected_tract'][-4:] if has_sel else 'Profile'}")
    
    m1, m2 = st.columns(2)
    m1.metric("Median Income", f"${disp['med_hh_income']:,.0f}")
    m2.metric("Poverty Rate", f"{disp['poverty_rate']:.1f}%")
    
    # Badges
    def badge(label, active):
        color = "#28a745" if active else "#6c757d"
        opacity = "1.0" if active else "0.4"
        return f'<div style="background-color:{color}; color:white; padding:5px; border-radius:5px; text-align:center; font-weight:bold; opacity:{opacity}; margin-bottom:5px;">{label}</div>'

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(badge("RURAL", disp['is_rural'] == 1), unsafe_allow_html=True)
        st.markdown(badge("OZ 2.0 ELIGIBLE", disp['Is_Eligible'] == 1), unsafe_allow_html=True)
    with c2:
        st.markdown(badge("NMTC ELIGIBLE", disp['nmtc_eligible'] == 1), unsafe_allow_html=True)
        st.markdown(badge("DEEP DISTRESS", disp['deep_distress'] == 1), unsafe_allow_html=True)

    st.markdown("---")
    if quota_remaining <= 0 and has_sel:
        st.warning("Quota reached for your account.")
    elif has_sel:
        with st.form("submission"):
            cat = st.selectbox("Category", ["Housing", "Healthcare", "Infrastructure", "Commercial", "Other"])
            notes = st.text_area("Justification / Notes")
            if st.form_submit_button("Submit Recommendation", use_container_width=True):
                try:
                    new_row = pd.DataFrame([{
                        "Date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                        "GEOID": disp['GEOID'],
                        "Category": cat,
                        "Justification": notes,
                        "Is_Eligible": int(disp['Is_Eligible']),
                        "User": st.session_state["username"]
                    }])
                    conn.create(spreadsheet=SHEET_URL, worksheet="Sheet1", data=new_row)
                    st.success("Recommendation Saved!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error saving: {e}")
    else:
        st.info("Select a tract on the map to begin recommendation.")

# --- 5. HISTORY TABLE ---
st.markdown("---")
st.subheader("📋 My Submission History")
if not recs.empty:
    user_recs = recs[recs['User'] == st.session_state["username"]]
    st.dataframe(user_recs, use_container_width=True, hide_index=True)