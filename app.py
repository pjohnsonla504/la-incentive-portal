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
    dphi, dlambda = np.radians(lat2 - l1), np.radians(lon2 - lon1)
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

# --- DATA LOADING ENGINES ---
@st.cache_data(ttl=60)
def load_data():
    def standardize_geoid(df, file_label):
        # Remove hidden spaces/weird characters from headers
        df.columns = [str(c).strip() for c in df.columns]
        
        # Look for the GEOID column using multiple possible aliases
        target = None
        aliases = ['geoid', 'fips', 'tract', 'id', 'geography']
        for c in df.columns:
            if any(a in c.lower() for a in aliases):
                target = c
                break
        
        if target:
            # Standardize the name to 'geoid_match' for the merge
            df = df.rename(columns={target: 'geoid_match'})
            # Ensure 11-digit string format
            df['geoid_match'] = df['geoid_match'].astype(str).str.replace(r'\.0$', '', regex=True).str.zfill(11)
            return df
        else:
            st.error(f"Critical Error: No GEOID/Tract column found in {file_label}. Columns available: {list(df.columns)}")
            st.stop()

    # Engine 1: Opportunity Zones 2.0 - Master Data File.csv
    elig_df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    elig_df = standardize_geoid(elig_df, "Master Data File")

    # Engine 2: Louisiana_All_Tracts_Demographics.csv
    demo_df = pd.read_csv("Louisiana_All_Tracts_Demographics.csv")
    demo_df = standardize_geoid(demo_df, "Demographics File")

    # Perform the Merge on the standardized key
    # 
    m = pd.merge(elig_df, demo_df, on="geoid_match", how="left", suffixes=('', '_demo'))
    m = m.rename(columns={'geoid_key': 'GEOID'}) # Maintain compatibility with existing UI logic

    # Clean numeric indicators
    nums = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus']
    for c in nums:
        # Find column regardless of case
        actual = next((col for col in m.columns if col.lower() == c), None)
        if actual:
            m[actual] = pd.to_numeric(m[actual].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # Engine 3: Anchors
    try:
        a = pd.read_csv("la_anchors.csv")
        a.columns = [c.strip().lower() for c in a.columns]
    except: a = pd.DataFrame(columns=['name', 'lat', 'lon', 'type'])

    # GeoJSON Engine
    with open("tl_2025_22_tract.json") as f: g = json.load(f)
    centroids = {}
    for feature in g['features']:
        coords = np.array(feature['geometry']['coordinates'][0])
        if coords.ndim == 3: coords = coords[0]
        centroids[feature['properties']['GEOID']] = [np.mean(coords[:, 1]), np.mean(coords[:, 0])]
    
    # Map coordinates to the merged dataframe
    m['lat'] = m['geoid_match'].map(lambda x: centroids.get(x, [0,0])[0])
    m['lon'] = m['geoid_match'].map(lambda x: centroids.get(x, [0,0])[1])
    
    return m, g, a

master_df, la_geojson, anchor_df = load_data()

# Identify the Eligibility column (Master Data File)
# Tracks highlighted green are only those eligible for the Opportunity Zone 2.0.
elig_col = next((c for c in master_df.columns if 'eligible' in c.lower() and 'nmtc' not in c.lower()), 'Is_Eligible')

# Filter by user assignment
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- QUOTA ---
try:
    recs = conn.read(worksheet="Sheet1", ttl=0)
    q_limit = max(1, int(len(master_df[master_df[elig_col] == 1]) * 0.25))
    q_rem = q_limit - len(recs[recs['User'] == st.session_state["username"]])
except: recs, q_limit, q_rem = pd.DataFrame(columns=["Date", "User", "GEOID", "Category", "Justification"]), 1, 1

# --- MAIN INTERFACE ---
st.title(f"📍 OZ 2.0 Portal: {st.session_state['a_val']}")
st.progress(min(1.0, (q_limit-q_rem)/q_limit)); st.write(f"Quota: {q_limit-q_rem} / {q_limit}")

c1, c2 = st.columns([0.6, 0.4])

with c1:
    p_col = next((c for c in master_df.columns if c.lower() == 'parish'), 'Parish')
    p_list = sorted(master_df[p_col].unique().tolist())
    sel_p = st.selectbox("Filter Parish", ["All"] + p_list)
    
    m_df = master_df.copy()
    if sel_p != "All": m_df = m_df[m_df[p_col] == sel_p]

    fig = px.choropleth_mapbox(
        m_df, geojson=la_geojson, locations="geoid_match", featureidkey="properties.GEOID",
        color=elig_col, color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
        mapbox_style="carto-positron", zoom=6, center={"lat": 31.0, "lon": -91.8},
        opacity=0.6, hover_data=["geoid_match"]
    )
    if not anchor_df.empty:
        fig.add_scattermapbox(lat=anchor_df['lat'], lon=anchor_df['lon'], mode='markers', marker=dict(size=10, color='#1E90FF'), text=anchor_df['name'])
    
    fig.update_layout(height=600, margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
    sel = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
    
    if sel and "selection" in sel and sel["selection"]["points"]:
        st.session_state["selected_tract"] = sel["selection"]["points"][0].get("location")

with c2:
    gid = st.session_state["selected_tract"]
    disp = master_df[master_df['geoid_match'] == gid].iloc[0] if gid else master_df.iloc[0]
    st.markdown(f"#### 📈 {'Tract '+gid[-4:] if gid else 'Select Tract'}")
    
    # Metric Display
    m1, m2, m3 = st.columns(3)
    def get_val(k):
        c = next((col for col in disp.index if col.lower() == k), None)
        return disp[c] if c else 0

    m1.metric("Pop", f"{get_val('pop_total'):,.0f}")
    m2.metric("Income", f"${get_val('med_hh_income'):,.0f}")
    m3.metric("Poverty", f"{get_val('poverty_rate'):.1f}%")

    st.divider()
    st.markdown("##### ⚓ 5 Closest Anchors")
    if gid and not anchor_df.empty:
        prox = anchor_df.copy()
        prox['dist'] = prox.apply(lambda r: get_distance(disp['lat'], disp['lon'], r['lat'], r['lon']), axis=1)
        for _, r in prox.sort_values('dist').head(5).iterrows():
            st.markdown(f"**{r['name']}** — {r['dist']:.2f} mi")

    with st.form("sub", clear_on_submit=True):
        st.write(f"Selected GEOID: {gid}")
        cat, notes = st.selectbox("Category", ["Housing", "Health", "Infra", "Comm", "Other"]), st.text_area("Justification")
        if st.form_submit_button("Submit Recommendation", use_container_width=True):
            if not gid: st.error("Please select a tract on the map first.")
            else:
                nr = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d"), "User": st.session_state["username"], "GEOID": gid, "Category": cat, "Justification": notes}])
                conn.update(worksheet="Sheet1", data=pd.concat([recs, nr], ignore_index=True))
                st.success("Recommendation saved successfully!"); st.cache_data.clear(); st.rerun()

st.divider()
st.subheader("📋 My Recommendation History")
st.dataframe(recs[recs['User'] == st.session_state["username"]], use_container_width=True, hide_index=True)