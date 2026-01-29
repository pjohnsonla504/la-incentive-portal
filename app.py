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

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# Distance Helper (Haversine)
def get_distance(lat1, lon1, lat2, lon2):
    r = 3958.8 # Miles
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- 2. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Recommendation Portal")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_in = st.text_input("Username").strip()
            p_in = st.text_input("Password", type="password").strip()
            if st.form_submit_button("Access Portal"):
                db = conn.read(worksheet="Users", ttl=0)
                db.columns = [c.strip() for c in db.columns]
                match = db[(db['Username'].astype(str) == u_in) & (db['Password'].astype(str) == p_in)]
                if not match.empty:
                    st.session_state.update({
                        "authenticated": True, "username": u_in, 
                        "role": str(match.iloc[0]['Role']), 
                        "a_type": str(match.iloc[0]['Assigned_Type']), 
                        "a_val": str(match.iloc[0]['Assigned_Value'])
                    })
                    st.rerun()
                else: st.error("Invalid credentials.")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    m = pd.read_csv("tract_data_final.csv")
    m.columns = [c.strip() for c in m.columns]
    m['GEOID'] = m['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    
    nums = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus', 'lat', 'lon']
    for c in nums:
        if c in m.columns:
            m[c] = pd.to_numeric(m[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    urb = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    m['is_rural'] = np.where((~m['Parish'].isin(urb)) & (m['pop_total'] < 5000), 1, 0)
    m['nmtc_eligible'] = np.where((m['poverty_rate'] >= 20) | (m['med_hh_income'] <= (m['med_hh_income'].median() * 0.8)), 1, 0)
    sev = (m['poverty_rate'] >= 30) | (m['med_hh_income'] <= (m['med_hh_income'].median() * 0.6)) | (m['unemp_rate'] >= 9.0)
    m['deep_distress'] = np.where((m['poverty_rate'] >= 40) | (m['med_hh_income'] <= (m['med_hh_income'].median() * 0.4)) | (m['unemp_rate'] >= 15.0) | ((m['is_rural'] == 1) & sev), 1, 0)

    with open("tl_2025_22_tract.json") as f: g = json.load(f)
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = [c.strip().lower() for c in a.columns]
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])
    return m, g, a

master_df, la_geojson, anchor_df = load_data()

if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- 4. RECOMMENDATIONS & QUOTA ---
try:
    recs = conn.read(worksheet="Sheet1", ttl=0)
    q_limit = max(1, int(len(master_df[master_df['Is_Eligible'] == 1]) * 0.25))
    q_rem = q_limit - len(recs[recs['User'] == st.session_state["username"]])
except: recs, q_limit, q_rem = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification", "Document"]), 1, 1

# --- 5. MAIN INTERFACE ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, (q_limit-q_rem)/q_limit)); st.write(f"**Recommendations:** {q_limit-q_rem} / {q_limit}")

c_map, c_met = st.columns([0.6, 0.4])

with c_map:
    f1, f2, f3 = st.columns(3)
    sel_p = f1.selectbox("Filter Parish", ["All"] + sorted(master_df['Parish'].unique().tolist()))
    only_elig = f2.toggle("Eligible Only")
    show_anchors = f3.toggle("Show Anchor Tags", value=True)

    m_df = master_df.copy()
    if sel_p != "All": m_df = m_df[m_df['Parish'] == sel_p]
    if only_elig: m_df = m_df[m_df['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", "Parish"]
    )

    if show_anchors and not anchor_df.empty:
        fig.add_scattermapbox(
            lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
            marker=dict(size=12, color='#1E90FF', opacity=0.9),
            text=anchor_df['name'], hoverinfo='text', name="Anchors", below='' 
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
    
    # ALL 7 INDICATORS
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
    
    # ANCHOR REPORT
    st.markdown("##### ⚓ 5 Closest Anchors")
    if has_sel and not anchor_df.empty:
        t_lat, t_lon = disp['lat'], disp['lon']
        # Calculate distances on the fly
        prox_df = anchor_df.copy()
        prox_df['dist'] = prox_df.apply(lambda row: get_distance(t_lat, t_lon, row['lat'], row['lon']), axis=1)
        prox_df = prox_df.sort_values('dist').head(5)
        
        for _, row in prox_df.iterrows():
            st.markdown(f"**{row['name']}** ({row['type']})  \n*{row['dist']:.2f} miles away*")
    else:
        st.write("Select a tract to view nearby anchors.")

    st.divider()
    
    # DESIGNATION STATUS
    def glow(l, a, c):
        bg = c if a else "#343a40"
        return f'<div style="background-color:{bg}; padding:8px; border-radius:6px; text-align:center; color:white; font-weight:bold; margin:2px; font-size:10px;">{l}</div>'

    st.markdown("##### 🏛️ Status")
    box1, box2 = st.columns(2)
    with box1:
        st.markdown(glow("URBAN", (disp['is_rural']==0 and has_sel), "#dc3545"), unsafe_allow_html=True)
        st.markdown(glow("RURAL", (disp['is_rural']==1 and has_sel), "#28a745"), unsafe_allow_html=True)
    with box2:
        st.markdown(glow("NMTC ELIGIBLE", (disp['nmtc_eligible']==1 and has_sel), "#28a745"), unsafe_allow_html=True)
        st.markdown(glow("DEEP DISTRESS", (disp['deep_distress']==1 and has_sel), "#28a745"), unsafe_allow_html=True)

    st.divider()
    with st.form("sub_form", clear_on_submit=True):
        gid = st.session_state["selected_tract"] if has_sel else "None"
        st.info(f"GEOID: {gid}")
        cat = st.selectbox("Category", ["Housing", "Healthcare", "Infrastructure", "Commercial", "Other"])
        notes = st.text_area("Justification")
        file = st.file_uploader("PDF Support", type=["pdf"])
        if st.form_submit_button("Submit Recommendation", use_container_width=True):
            if not has_sel: st.error("Select a tract.")
            elif q_rem <= 0: st.warning("Quota reached.")
            else:
                nr = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": gid, "Category": cat, "Justification": notes, "Document": (file.name if file else "None")}])
                conn.update(worksheet="Sheet1", data=pd.concat([recs, nr], ignore_index=True))
                st.success("Recorded."); st.cache_data.clear(); st.rerun()

# 6. HISTORY SECTION (AT BOTTOM)
st