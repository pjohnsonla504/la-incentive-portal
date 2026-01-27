import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="OZ 2.0 Recommendation Portal", layout="wide")

# Connection established using the service_account secret
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Connection failed. Please check your Secrets formatting.")
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
            u_input = st.text_input("Username")
            p_input = st.text_input("Password", type="password")
            if st.form_submit_button("Access Portal"):
                user_db = conn.read(worksheet="Users", ttl=0)
                user_db.columns = [str(c).strip() for c in user_db.columns]
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
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    cols_to_fix = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus']
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

if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# Quota Logic
try:
    existing_recs = conn.read(worksheet="Sheet1", ttl=0)
    eligible_count = len(master_df[master_df['Is_Eligible'] == 1])
    quota_limit = max(1, int(eligible_count * 0.25))
    current_usage = len(existing_recs[existing_recs['User'] == st.session_state["username"]])
    quota_remaining = quota_limit - current_usage
except:
    existing_recs, quota_limit, current_usage, quota_remaining = pd.DataFrame(), 0, 0, 0

# --- 4. LAYOUT ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")

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
    
    # Per instructions: Highlights are only for OZ 2.0 eligible tracks
    if only_elig:
        map_df = map_df[map_df['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(
        map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )
    fig.update_layout(height=700, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')
    
    selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
        st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

with col_metrics:
    has_sel = st.session_state["selected_tract"] is not None
    disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0] if has_sel else master_df.iloc[0]
    lbl = f"Tract {st.session_state['selected_tract'][-4:]}" if has_sel else "Select a Tract"

    st.markdown(f"#### 📈 {lbl} Profile")
    m_top = st.columns(3)
    m_top[0].metric("Pop", f"{disp['pop_total']:,.0f}")
    m_top[1].metric("Income", f"${disp['med_hh_income']:,.0f}")
    m_top[2].metric("Poverty", f"{disp['poverty_rate']:.1f}%")

    m_bot = st.columns(4)
    m_bot[0].metric("Unemp", f"{disp['unemp_rate']:.1f}%")
    m_bot[1].metric("Student", f"{disp['age_18_24_pct']:.1f}%")
    m_bot[2].metric("HS Grad", f"{disp['hs_plus_pct_25plus']:.1f}%")
    m_bot[3].metric("BA Grad", f"{disp['ba_plus_pct_25plus']:.1f}%")

    st.divider()
    def glow_box(label, active, active_color="#28a745"):
        bg = active_color if active else "#343a40"
        shadow = f"0px 0px 10px {active_color}" if active else "none"
        opac = "1.0" if active else "0.3"
        return f"""<div style="background-color:{bg}; padding:8px; border-radius:6px; text-align:center; color:white; font-weight:bold; box-shadow:{shadow}; opacity:{opac}; margin:2px; font-size:10px; min-height:40px; display:flex; align-items:center; justify-content:center;">{label}</div>"""

    st.markdown("##### 🏛️ Designation Status")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(glow_box("URBAN", (disp['is_rural']==0 and has_sel), "#dc3545"), unsafe_allow_html=True)
        st.markdown(glow_box("RURAL", (disp['is_rural']==1 and has_sel), "#28a745"), unsafe_allow_html=True)
    with c2:
        st.markdown(glow_box("NMTC ELIGIBLE", (disp['nmtc_eligible']==1 and has_sel), "#28a745"), unsafe_allow_html=True)
        st.markdown(glow_box("NMTC DEEP DISTRESS", (disp['deep_distress']==1 and has_sel), "#28a745"), unsafe_allow_html=True)

    # --- RECORD RECOMMENDATION ---
    st.divider()
    st.markdown("##### 📝 Record Recommendation")
    if quota_remaining <= 0 and has_sel:
        st.warning("Quota reached for this region.")
    else:
        with st.form("sub_form", clear_on_submit=True):
            f_c1, f_c2 = st.columns([1, 1])
            geoid_val = st.session_state["selected_tract"] if has_sel else "None Selected"
            f_c1.info(f"GEOID: {geoid_val}")
            cat = f_c2.selectbox("Category", ["Housing", "Healthcare", "Infrastructure", "Commercial", "Other"], label_visibility="collapsed")
            notes = st.text_area("Justification", height=100, placeholder="Enter justification...")
            
            if st.form_submit_button("Submit Recommendation", use_container_width=True):
                if not has_sel: 
                    st.error("Please select a tract.")
                else:
                    new_row = pd.DataFrame([{
                        "Date": pd.Timestamp.now().strftime("%Y-%m-%d"), 
                        "User": st.session_state["username"], 
                        "GEOID": geoid_val, 
                        "Category": cat, 
                        "Justification": notes
                    }])
                    updated_df = pd.concat([existing_recs, new_row], ignore_index=True)
                    conn.update(worksheet="Sheet1", data=updated_df)
                    st.success(f"Entry Recorded for {geoid_val}")
                    st.cache_data.clear()
                    st.rerun()

# --- RUNNING TRACT LIST ---
st.divider()
st.subheader("📋 My Recommended Tracts")
try:
    user_recs = existing_recs[existing_recs['User'] == st.session_state["username"]]
    st.dataframe(user_recs, use_container_width=True, hide_index=True)
except:
    st.info("Your recommendations will appear here.")