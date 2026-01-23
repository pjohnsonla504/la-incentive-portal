import streamlit as st
import pandas as pd
import plotly.express as px
import json
import numpy as np
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

# --- 2. AUTHENTICATION ---
if not st.session_state["authenticated"]:
    st.title("🔐 LA Incentive Portal Login")
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

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # Sanitizing Economics
    cols_to_fix = ['poverty_rate', 'unemp_rate', 'med_hh_income']
    for col in cols_to_fix:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# --- 4. TERRITORY ISOLATION ---
if st.session_state["role"].lower() != "admin" and st.session_state["a_type"].lower() != "all":
    a_type = st.session_state["a_type"]
    a_val = st.session_state["a_val"]
    if a_type in master_df.columns:
        master_df = master_df[master_df[a_type] == a_val]

# --- 5. SMART CENTERING (GEOJSON Fallback) ---
def get_map_center(current_df, geojson_data):
    # If lat/lon exists in CSV, use that (fastest)
    if 'lat' in current_df.columns and 'lon' in current_df.columns:
        return {"lat": current_df['lat'].mean(), "lon": current_df['lon'].mean()}
    
    # Otherwise, extract from GeoJSON based on filtered GEOIDs
    visible_geoids = set(current_df['GEOID'].unique())
    lats, lons = [], []
    
    for feature in geojson_data['features']:
        if feature['properties']['GEOID'] in visible_geoids:
            geometry = feature['geometry']
            if geometry['type'] == 'Polygon':
                coords = np.array(geometry['coordinates'][0])
                lons.extend(coords[:, 0])
                lats.extend(coords[:, 1])
            elif geometry['type'] == 'MultiPolygon':
                for poly in geometry['coordinates']:
                    coords = np.array(poly[0])
                    lons.extend(coords[:, 0])
                    lats.extend(coords[:, 1])
    
    if lats and lons:
        return {"lat": np.mean(lats), "lon": np.mean(lons)}
    return {"lat": 31.0, "lon": -91.8} # Default LA center

# --- 6. TOP METRICS & ECONOMIC SNAPSHOT ---
st.title(f"📍 {st.session_state['a_val']} Analysis Portal")
l_col, r_col = st.columns(2)

with l_col:
    st.subheader("Portal Statistics")
    m1, m2, m3 = st.columns(3)
    m1.metric("Tracts", len(master_df))
    m2.metric("Eligible (OZ 2.0)", len(master_df[master_df['Is_Eligible'] == 1]))
    try:
        all_recs = conn.read(worksheet="Sheet1", ttl=0)
        m3.metric("Total Recs", len(all_recs))
    except:
        all_recs = pd.DataFrame()
        m3.metric("Total Recs", 0)

with r_col:
    st.subheader("Economic Snapshot")
    if st.session_state["selected_tract"] and st.session_state["selected_tract"] in master_df['GEOID'].values:
        disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0]
        lbl, is_s = f"Tract {st.session_state['selected_tract'][-4:]}", True
    else:
        disp, lbl, is_s = master_df, "Area Avg", False

    e1, e2, e3 = st.columns(3)
    def get_val(col):
        if col not in master_df.columns: return 0.0
        return float(disp[col]) if is_s else float(disp[col].mean())

    e1.metric(f"{lbl} Poverty", f"{get_val('poverty_rate'):.1f}%")
    e2.metric(f"{lbl} Unemp.", f"{get_val('unemp_rate'):.1f}%")
    e3.metric(f"{lbl} Income", f"${get_val('med_hh_income'):,.0f}")

# --- 7. MAP & DYNAMIC ZOOM ---
st.divider()
with st.expander("Map Filters & Search", expanded=False):
    f1, f2 = st.columns(2)
    with f1:
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Isolate Specific Parish", options=p_list)
    with f2:
        only_elig = st.toggle("Highlight Only Eligible Tracks (Green)")

map_df = master_df.copy()
if sel_parish != "All Authorized Parishes":
    map_df = map_df[map_df['Parish'] == sel_parish]
    zoom_lvl = 9.5
elif st.session_state["role"].lower() != "admin":
    zoom_lvl = 7.5
else:
    zoom_lvl = 6.0

# Get center based on the current visible map_df
center_coords = get_map_center(map_df, la_geojson)

if only_elig:
    map_df = map_df[map_df['Is_Eligible'] == 1]

fig = px.choropleth_mapbox(
    map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
    color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
    mapbox_style="carto-positron", zoom=zoom_lvl, center=center_coords,
    opacity=0.6, hover_data=["GEOID", "Parish"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')

selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")
if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
    st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

# --- 8. SUBMISSION FORM ---
st.divider()
st.subheader("Submit Recommendation")
all_geoids = sorted(master_df['GEOID'].unique().tolist())
default_index = all_geoids.index(st.session_state["selected_tract"]) if st.session_state["selected_tract"] in all_geoids else 0

with st.form("sub_form", clear_on_submit=True):
    geoid = st.selectbox("Tract GEOID", options=all_geoids, index=default_index)
    cat = st.selectbox("Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    notes = st.text_area("Justification")
    if st.form_submit_button("Record Recommendation"):
        match = master_df.loc[master_df['GEOID'] == geoid, 'Is_Eligible']
        elig_label = "Eligible" if (not match.empty and match.values[0] == 1) else "Ineligible"
        new_row = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "User": st.session_state["username"], "GEOID": geoid, "Category": cat, "Justification": notes, "Is_Eligible": elig_label}])
        old_data = conn.read(worksheet="Sheet1", ttl=0)
        conn.update(worksheet="Sheet1", data=pd.concat([old_data, new_row], ignore_index=True))
        st.success(f"✅ Success! Captured {geoid}.")
        st.session_state["selected_tract"] = None
        st.balloons()

# --- 9. ACTIVITY LOG ---
st.divider()
if not all_recs.empty:
    user_view = all_recs if st.session_state["role"].lower() == "admin" else all_recs[all_recs['User'] == st.session_state['username']]
    st.dataframe(user_view, use_container_width=True, hide_index=True)