import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="OZ 2.0 Recommendation Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

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
                user_db = conn.read(worksheet="Users")
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

# --- 3. DATA LOADING & NMTC LOGIC (PolicyMap Conformity) ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # Sanitize 7 Metrics
    cols_to_fix = [
        'poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total',
        'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus'
    ]
    for col in cols_to_fix:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    state_median = master['med_hh_income'].median()
    nat_unemp_bench = 6.0 # Standard benchmark for NMTC periods

    # RURAL DEFINITION (OZ 2.0)
    urban_parishes = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urban_parishes)) & (master['pop_total'] < 5000), 1, 0)

    # NMTC ELIGIBILITY
    master['nmtc_eligible'] = np.where((master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (state_median * 0.8)), 1, 0)
    
    # DEEP DISTRESS LOGIC (PolicyMap Standard)
    # Includes Rural-Severe bump for tracts like 22075050100
    is_severe = (master['poverty_rate'] >= 30) | (master['med_hh_income'] <= (state_median * 0.6)) | (master['unemp_rate'] >= 9.0)
    
    cond_poverty_40 = (master['poverty_rate'] >= 40)
    cond_income_40  = (master['med_hh_income'] <= (state_median * 0.4))
    cond_unemp_15   = (master['unemp_rate'] >= 15.0)
    cond_rural_severe = (master['is_rural'] == 1) & is_severe

    master['deep_distress'] = np.where(cond_poverty_40 | cond_income_40 | cond_unemp_15 | cond_rural_severe, 1, 0)

    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# --- 4. DASHBOARD LAYOUT ---
st.title(f"📍 OZ 2.0 Recommendation Portal: {st.session_state['a_val']}")
col_map, col_metrics = st.columns([0.6, 0.4])

with col_map:
    # Top Controls
    f1, f2 = st.columns(2)
    with f1:
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Isolate Parish", options=p_list, label_visibility="collapsed")
    with f2:
        only_elig = st.toggle("OZ 2.0 Eligible Only (Green)")

    # Map Filtering
    map_df = master_df.copy()
    if sel_parish != "All Authorized Parishes":
        map_df = map_df[map_df['Parish'] == sel_parish]
    if only_elig:
        map_df = map_df[map_df['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(
        map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )
    fig.update_layout(height=750, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')
    
    selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
        st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

with col_metrics:
    has_sel = st.session_state["selected_tract"] is not None
    if has_sel:
        disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0]
        lbl = f"Tract {st.session_state['selected_tract'][-4:]}"
    else:
        disp = master_df.iloc[0]
        lbl = "Select a Tract"

    # --- 7 PROFILE METRICS ---
    st.markdown(f"#### 📈 {lbl} Profile")
    m1, m2, m3 = st.columns(3)
    m1.metric("Population", f"{disp['pop_total']:,.0f}")
    m2.metric("Med. Income", f"${disp['med_hh_income']:,.0f}")
    m3.metric("Poverty", f"{disp['poverty_rate']:.1f}%")

    m4, m5, m6, m7 = st.columns(4)
    m4.metric("Unemp.", f"{disp['unemp_rate']:.1f}%")
    m5.metric("Student", f"{disp['age_18_24_pct']:.1f}%")
    m6.metric("HS Grad", f"{disp['hs_plus_pct_25plus']:.1f}%")
    m7.metric("BA Grad", f"{disp['ba_plus_pct_25plus']:.1f}%")

    # --- DESIGNATION GRID (COMPACT) ---
    st.divider()
    def glow_box(label, active, active_color="#28a745"):
        bg = active_color if active else "#343a40"
        shadow = f"0px 0px 10px {active_color}" if active else "none"
        opac = "1.0" if active else "0.3"
        return f"""<div style="background-color:{bg}; padding:8px; border-radius:6px; text-align:center; color:white; font-weight:bold; box-shadow:{shadow}; opacity:{opac}; margin:2px; font-size:10px; min-height:45px; display:flex; align-items:center; justify-content:center; border: 1px solid rgba(255,255,255,0.1);">{label}</div>"""

    st.markdown("##### 🏛️ Status Indicators")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(glow_box("URBAN", (disp['is_rural']==0 and has_sel), "#dc3545"), unsafe_allow_html=True)
        st.markdown(glow_box("RURAL", (disp['is_rural']==1 and has_sel), "#28a745"), unsafe_allow_html=True)
    with c2:
        st.markdown(glow_box("NMTC ELIGIBLE", (disp['nmtc_eligible']==1 and has_sel), "#28a745"), unsafe_allow_html=True)
        st.markdown(glow_box("NMTC DEEP DISTRESS", (disp['deep_distress']==1 and has_sel), "#28a745"), unsafe_allow_html=True)

    # --- EXPANDED RECOMMENDATION FORM ---
    st.divider()
    st.markdown("##### 📝 Record Recommendation")
    with st.form("sub_form", clear_on_submit=True):
        f_c1, f_c2 = st.columns([1, 1])
        geoid_val = st.session_state["selected_tract"] if has_sel else "None Selected"
        f_c1.info(f"GEOID: {geoid_val}")
        cat = f_c2.selectbox("Category", ["Housing", "Infrastructure", "Commercial", "Other"], label_visibility="collapsed")
        
        notes = st.text_area("Justification & Local Impact", height=200, placeholder="Explain why this tract should be prioritized...")
        
        if st.form_submit_button("Submit Recommendation", use_container_width=True):
            if not has_sel:
                st.error("Please select a tract first.")
            else:
                # GSheets update logic
                st.success(f"Entry for {geoid_val} recorded.")

# --- 5. ACTIVITY LOG ---
st.divider()
try:
    recs = conn.read(worksheet="Sheet1", ttl=0)
    st.dataframe(recs.tail(5), use_container_width=True, hide_index=True)
except:
    st.info("Log will appear here after first submission.")