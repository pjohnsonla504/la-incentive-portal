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
    st.error(f"Config Error: {e}"); st.stop()

# Initialize Session States
if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

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
                    match = user_db[(user_db['Username'].astype(str) == u_in) & (user_db['Password'].astype(str) == p_in)]
                    if not match.empty:
                        st.session_state.update({
                            "authenticated": True, "username": u_in, 
                            "role": str(match.iloc[0]['Role']).strip(), 
                            "a_type": str(match.iloc[0]['Assigned_Type']).strip(), 
                            "a_val": str(match.iloc[0]['Assigned_Value']).strip()
                        })
                        st.rerun()
                    else: st.error("Invalid credentials.")
                except Exception as e: st.error(f"Login Error: {e}")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    # Process all 7 indicators
    num_cols = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus']
    for c in num_cols:
        master[c] = pd.to_numeric(master[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    s_med = master['med_hh_income'].median()
    urb_p = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urb_p)) & (master['pop_total'] < 5000), 1, 0)
    master['nmtc_eligible'] = np.where((master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (s_med * 0.8)), 1, 0)
    sev = (master['poverty_rate'] >= 30) | (master['med_hh_income'] <= (s_med * 0.6)) | (master['unemp_rate'] >= 9.0)
    master['deep_distress'] = np.where((master['poverty_rate'] >= 40) | (master['med_hh_income'] <= (s_med * 0.4)) | (master['unemp_rate'] >= 15.0) | ((master['is_rural'] == 1) & sev), 1, 0)

    with open("tl_2025_22_tract.json") as f: geojson = json.load(f)
    try: anchors = pd.read_csv("la_anchors.csv")
    except: anchors = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
    return master, geojson, anchors

master_df, la_geojson, anchor_df = load_data()

# Authorization Filter
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- 4. RECOMMENDATIONS & QUOTA ---
try:
    existing_recs = conn.read(worksheet="Sheet1", ttl=0)
    q_limit = max(1, int(len(master_df[master_df['Is_Eligible'] == 1]) * 0.25))
    curr_use = len(existing_recs[existing_recs['User'] == st.session_state["username"]])
    q_rem = q_limit - curr_use
except: existing_recs, q_limit, curr_use, q_rem = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification", "Document"]), 1, 0, 1

# --- 5. MAIN INTERFACE ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, curr_use / q_limit) if q_limit > 0 else 0)
st.write(f"**Recommendations:** {curr_use} / {q_limit}")

c_map, c_met = st.columns([0.6, 0.4])

with c_map:
    f1, f2, f3 = st.columns(3)
    sel_p = f1.selectbox("Filter Parish", ["All"] + sorted(master_df['Parish'].unique().tolist()))
    only_elig = f2.toggle("Eligible Only")
    show_anchors = f3.toggle("Show Anchor Tags", value=True)

    map_df = master_df.copy()
    if sel_p != "All": map_df = map_df[map_df['Parish'] == sel_p]
    if only_elig: map_df = map_df[map_df['Is_Eligible'] == 1]

    # Base Choropleth (Tracts)
    fig = px.choropleth_mapbox(
        map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )

    # Permanent Anchor Tags (Visible at all zoom levels)
    if show_anchors and not anchor_df.empty:
        fig.add_scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=12, color='#1E90FF', opacity=1.0, symbol='circle'), # Increased size
            text=anchor_df['name'] + " (" + anchor_df['type'] + ")",
            hoverinfo='text', name="Anchors", below='' 
        )

    fig.update_layout(height=650, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select', showlegend=False)
    sel_pts = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if sel_pts and "selection" in sel_pts and len(sel_pts["selection"]["points"]) > 0:
        loc = sel_pts["selection"]["points"][0].get("location")
        if loc: st.session_state["selected_tract"] = loc

with c_met:
    has_sel = st.session_state["selected_tract"] is not None
    disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0] if has_sel else master_df.iloc[0]
    lbl = f"Tract {st.session_state['selected_tract'][-4:]}" if has_sel else "Select a Tract"

    st.markdown(f"#### 📈 {lbl} Profile")
    
    # --- 7 Indicators Grid ---
    m1, m2, m3 = st.columns(3)
    m1.metric("Pop", f"{disp['pop_total']:,.0f}")
    m2.metric("Income", f"${disp['med_hh_income']:,.0f}")
    m3.metric("Poverty", f"{disp['poverty_rate']:.1f}%")

    m4, m5 = st.columns(2)
    m4.metric("Unemployment", f"{disp['unemp_rate']:.1f}%")
    m5.metric("Student (18-24)", f"{disp['age_18_24_pct']:.1f}%")
    
    m6, m7 = st.columns(2)
    m6.metric("HS Grad Rate", f"{disp['hs_plus_pct_25plus']:.1f}%")
    m7.metric("BA+ Grad Rate", f"{disp['ba_plus_pct_25plus']:.1f}%")

    st.divider()
    # --- Designation Glow Boxes ---
    def glow(label, active, color):
        bg = color if active else "#343a40"
        return f'<div style="background-color:{bg}; padding:8px; border-radius:6px; text-align:center; color:white; font-weight:bold; margin:2px; font-size:10px; min-height:40px; display:flex; align-items:center; justify-content:center;">{label}</div>'

    st.markdown("##### 🏛️ Designation Status