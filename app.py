import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA OZ 2.0 Portal", layout="wide")

try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error(f"Config Error: {e}"); st.stop()

if "authenticated" not in st.session_state:
    st.session_state.update({"authenticated": False, "selected_tract": None})

def get_distance(lat1, lon1, lat2, lon2):
    r = 3958.8 
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi, dlambda = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dphi/2)**2 + np.cos(phi1)*np.cos(phi2)*np.sin(dlambda/2)**2
    return r * 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))

# --- AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 Louisiana OZ 2.0 Portal")
    with st.form("login"):
        u_in, p_in = st.text_input("User").strip(), st.text_input("Pass", type="password").strip()
        if st.form_submit_button("Access"):
            db = conn.read(worksheet="Users", ttl=0)
            db.columns = [c.strip() for c in db.columns]
            match = db[(db['Username'].astype(str)==u_in) & (db['Password'].astype(str)==p_in)]
            if not match.empty:
                st.session_state.update({"authenticated": True, "username": u_in, "role": str(match.iloc[0]['Role']), "a_type": str(match.iloc[0]['Assigned_Type']), "a_val": str(match.iloc[0]['Assigned_Value'])})
                st.rerun()
    st.stop()

# --- DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    def force_geoid_column(df, filename):
        df.columns = [str(c).strip().lower() for c in df.columns]
        target = None
        # Priority search for GEOID
        for key in ['geoid', 'tract', 'fips']:
            for c in df.columns:
                if key == c or key in c:
                    target = c
                    break
            if target: break
        
        if target:
            df = df.rename(columns={target: 'geoid_internal'})
            df['geoid_internal'] = df['geoid_internal'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
            return df
        else:
            st.error(f"❌ Error in **{filename}**: Found columns: {list(df.columns)}")
            st.stop()

    # Engine 1: Eligibility (Master Data)
    elig_df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    elig_df = force_geoid_column(elig_df, "Master Data File")
    
    # Engine 2: Demographics
    demo_df = pd.read_csv("Louisiana_All_Tracts_Demographics.csv")
    demo_df = force_geoid_column(demo_df, "Demographics File")
    
    # Merge on the unified internal key
    m = pd.merge(elig_df, demo_df, on="geoid_internal", how="left", suffixes=('', '_demo'))
    m = m.rename(columns={'geoid_internal': 'GEOID'})

    # Clean metrics
    metrics = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus']
    for met in metrics:
        if met in m.columns:
            m[met] = pd.to_numeric(m[met].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # Engine 3: Anchors
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = [c.strip().lower() for c in a.columns]
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    # GeoJSON Logic
    with open("tl_2025_22_tract.json") as f: g = json.load(f)
    centroids = {}
    for feature in g['features']:
        gid = feature['properties']['GEOID']
        coords = np.array(feature['geometry']['coordinates'][0])
        if coords.ndim == 3: coords = coords[0]
        centroids[gid] = [np.mean(coords[:, 1]), np.mean(coords[:, 0])]
    
    m['lat'] = m['GEOID'].map(lambda x: centroids.get(x, [0,0])[0])
    m['lon'] = m['GEOID'].map(lambda x: centroids.get(x, [0,0])[1])
    
    return m, g, a

master_df, la_geojson, anchor_df = load_data()

# Find Eligibility Column
elig_col = next((c for c in master_df.columns if 'eligible' in c and 'nmtc' not in c), None)
if not elig_col:
    master_df['Is_Eligible'] = 1
    elig_col = 'Is_Eligible'

# Find Parish Column and Clean it for sorting
p_col = next((c for c in master_df.columns if 'parish' in c), None)
if p_col:
    master_df[p_col] = master_df[p_col].fillna("Unknown").astype(str)
else:
    master_df['Parish_Default'] = "Unknown"
    p_col = 'Parish_Default'

# Apply Role Filters
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- QUOTA ---
try:
    recs = conn.read(worksheet="Sheet1", ttl=0)
    # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0.
    q_limit = max(1, int(len(master_df[master_df[elig_col] == 1]) * 0.25))
    q_rem = q_limit - len(recs[recs['User'] == st.session_state["username"]])
except: recs, q_limit, q_rem = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification"]), 1, 1

# --- INTERFACE ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, (q_limit-q_rem)/q_limit)); st.write(f"Recommendations: {q_limit-q_rem} / {q_limit}")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    p_list = sorted(master_df[p_col].unique().tolist())
    sel_p = st.selectbox("Filter Parish", ["All"] + p_list)
    
    m_df = master_df.copy()
    if sel_p != "All": m_df = m_df[m_df[p_col] == sel_p]

    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
        color=elig_col, color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["GEOID", p_col]
    )
    if not anchor_df.empty:
        fig.add_scattermapbox(lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers', marker=dict(size=10, color='#1E90FF'), text=anchor_df['name'])
    
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    if sel and "selection" in sel and sel["selection"]["points"]:
        st.session_state["selected_tract"] = sel["selection"]["points"][0].get("location")

with c2:
    gid = st.session_state["selected_tract"]
    # Check if selected tract exists in current filtered dataframe
    disp_df = master_df[master_df['GEOID'] == gid]
    disp = disp_df.iloc[0] if not disp_df.empty else master_df.iloc[0]
    
    st.markdown(f"#### 📈 {'Tract '+gid[-4:] if gid else 'Select Tract'}")
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Pop", f"{disp.get('pop_total', 0):,.0f}")
    m2.metric("Income", f"${disp.get('med_hh_income', 0):,.0f}")
    m3.metric("Poverty", f"{disp.get('poverty_rate', 0):.1f}%")

    st.divider()
    st.markdown("##### ⚓ 5 Closest Anchors")
    if gid and not anchor_df.empty:
        prox = anchor_df.copy()
        prox['dist'] = prox.apply(lambda r: get_distance(disp['lat'], disp['lon'], r['lat'], r['lon']), axis=1)
        for _, r in prox.sort_values('dist').head(5).iterrows():
            st.markdown(f"**{r['name']}** — {r['dist']:.2f} mi")

    with st.form("sub"):
        st.write(f"Selected: {gid}")
        cat, notes = st.selectbox("Category", ["Housing", "Health", "Infra", "Comm", "Other"]), st.text_area("Justification")
        if st.form_submit_button("Submit"):
            if not gid: st.error("Select tract on map.")
            else:
                nr = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": gid, "Category": cat, "Justification": notes}])
                conn.update(worksheet="Sheet1", data=pd.concat([recs, nr], ignore_index=True))
                st.success("Saved!"); st.cache_data.clear(); st.rerun()

st.subheader("📋 My History")
st.dataframe(recs[recs['User'] == st.session_state["username"]], use_container_width=True)