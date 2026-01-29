import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="OZ 2.0 Portal", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

# --- AUTH ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login_form"):
        u_in, p_in = st.text_input("User"), st.text_input("Pass", type="password")
        if st.form_submit_button("Login"):
            db = conn.read(worksheet="Users", ttl=0)
            db.columns = [c.strip() for c in db.columns]
            match = db[(db['Username'].astype(str)==u_in.strip()) & (db['Password'].astype(str)==p_in.strip())]
            if not match.empty:
                st.session_state.update({"authenticated":True, "username":u_in, "role":str(match.iloc[0]['Role']), "a_type":str(match.iloc[0]['Assigned_Type']), "a_val":str(match.iloc[0]['Assigned_Value'])})
                st.rerun()
            else: st.error("Invalid credentials")
    st.stop()

# --- DATA ---
@st.cache_data(ttl=60)
def load_all():
    m = pd.read_csv("tract_data_final.csv")
    m.columns = [c.strip() for c in m.columns]
    m['GEOID'] = m['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
    nums = ['poverty_rate','unemp_rate','med_hh_income','pop_total','age_18_24_pct','hs_plus_pct_25plus','ba_plus_pct_25plus']
    for c in nums: m[c] = pd.to_numeric(m[c].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    urb = ['Orleans','Jefferson','East Baton Rouge','Caddo','Lafayette','St. Tammany']
    m['is_rural'] = np.where((~m['Parish'].isin(urb)) & (m['pop_total'] < 5000), 1, 0)
    m['nmtc_eligible'] = np.where((m['poverty_rate'] >= 20) | (m['med_hh_income'] <= (m['med_hh_income'].median() * 0.8)), 1, 0)
    
    with open("tl_2025_22_tract.json") as f: g = json.load(f)
    try: a = pd.read_csv("la_anchors.csv")
    except: a = pd.DataFrame(columns=['name','lat','lon','type'])
    return m, g, a

master_df, la_geojson, anchor_df = load_all()
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- QUOTA ---
try:
    recs = conn.read(worksheet="Sheet1", ttl=0)
    q_limit = max(1, int(len(master_df[master_df['Is_Eligible']==1]) * 0.25))
    u_recs = recs[recs['User'] == st.session_state["username"]]
    q_rem = q_limit - len(u_recs)
except: recs, q_limit, q_rem = pd.DataFrame(columns=["Date","User","GEOID","Category","Justification","Document"]), 1, 1

# --- UI ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, (q_limit-q_rem)/q_limit)); st.write(f"Quota: {q_limit-q_rem} / {q_limit}")

c1, c2 = st.columns([0.6, 0.4])
with c1:
    f_p, f_e, f_a = st.columns(3)
    sel_p = f_p.selectbox("Parish", ["All"] + sorted(master_df['Parish'].unique().tolist()))
    only_e = f_e.toggle("Eligible Only")
    show_a = f_a.toggle("Show Anchors", True)
    
    df_m = master_df.copy()
    if sel_p != "All": df_m = df_m[df_m['Parish'] == sel_p]
    if only_e: df_m = df_m[df_m['Is_Eligible'] == 1]

    fig = px.choropleth_mapbox(df_m, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
                               color="Is_Eligible", color_continuous_scale=[(0,"#6c757d"),(1,"#28a745")],
                               mapbox_style="carto-positron", zoom=6, center={"lat":31,"lon":-91.8}, opacity=0.6)
    if show_a and not anchor_df.empty:
        fig.add_scattermapbox(lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers',
                              marker=dict(size=6, color='#0047AB'), text=anchor_df['name'], below='')
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if sel and "selection" in sel and sel["selection"]["points"]:
        loc = sel["selection"]["points"][0].get("location")
        if loc: st.session_state["selected_tract"] = loc

with c2:
    gid = st.session_state["selected_tract"]
    disp = master_df[master_df['GEOID']==gid].iloc[0] if gid else master_df.iloc[0]
    st.markdown(f"#### 📈 {'Tract ' + gid[-4:] if gid else 'Select Tract'}")
    
    m_cols = st.columns(3)
    m_cols[0].metric("Pop", f"{disp['pop_total']:,.0f}")
    m_cols[1].metric("Inc", f"${disp['med_hh_income']:,.0f}")
    m_cols[2].metric("Pov", f"{disp['poverty_rate']}%")
    
    st.write(f"Unemp: {disp['unemp_rate']}% | HS: {disp['hs_plus_pct_25plus']}% | BA: {disp['ba_plus_pct_25plus']}%")
    
    with st.form("sub"):
        st.write(f"GEOID: {gid}")
        cat = st.selectbox("Type", ["Housing","Health","Infra","Comm","Other"])
        txt = st.text_area("Justification")
        file = st.file_uploader("PDF", type="pdf")
        if st.form_submit_button("Submit"):
            if not gid: st.error("Select tract")
            elif q_rem <= 0: st.error("Quota full")
            else:
                nr = pd.DataFrame([{"Date":pd.Timestamp.now().strftime("%Y-%m-%d"), "User":st.session_state["username"], "GEOID":gid, "Category":cat, "Justification":txt, "Document":(file.name if file else "None")}])
                conn.update(worksheet="Sheet1", data=pd.concat([recs, nr]))
                st.success("Saved"); st.cache_data.clear(); st.rerun()

st.subheader("📋 History")
st.dataframe(recs[recs['User']==st.session_state["username"]], use_container_width=True)