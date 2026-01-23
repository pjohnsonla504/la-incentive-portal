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
    
    cols_to_fix = [
        'poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total', 
        'age_18_24_pct', 'hs_plus_pct_25plus', 'ba_plus_pct_25plus'
    ]
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

# --- 5. SMART CENTERING UTILITY ---
def get_map_center(current_df, geojson_data):
    if 'lat' in current_df.columns and 'lon' in current_df.columns:
        return {"lat": current_df['lat'].mean(), "lon": current_df['lon'].mean()}
    
    visible_geoids = set(current_df['GEOID'].unique())
    lats, lons = [], []
    for feature in geojson_data['features']:
        if feature['properties']['GEOID'] in visible_geoids:
            geometry = feature['geometry']
            if geometry['type'] == 'Polygon':
                coords = np.array(geometry['coordinates'][0])
                lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
            elif geometry['type'] == 'MultiPolygon':
                for poly in geometry['coordinates']:
                    coords = np.array(poly[0])
                    lons.extend(coords[:, 0]); lats.extend(coords[:, 1])
    return {"lat": np.mean(lats), "lon": np.mean(lons)} if lats else {"lat": 31.0, "lon": -91.8}

# --- 6. MAIN DASHBOARD ---
st.title(f"📍 {st.session_state['a_val']} Incentive Portal")

# Use a standard wide layout for the top section
col_map, col_metrics = st.columns([0.5, 0.5])

with col_map:
    f1, f2 = st.columns(2)
    with f1:
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Isolate Parish", options=p_list)
    with f2:
        only_elig = st.toggle("Show Eligible Only (Green)")

    map_df = master_df.copy()
    if sel_parish != "All Authorized Parishes":
        map_df = map_df[map_df['Parish'] == sel_parish]
        zoom_lvl = 9.5
    else:
        zoom_lvl = 7.5 if st.session_state["role"].lower() != "admin" else 6.0

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

with col_metrics:
    # Set the data context
    if st.session_state["selected_tract"] and st.session_state["selected_tract"] in master_df['GEOID'].values:
        disp = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0]
        lbl, is_s = f"Tract {st.session_state['selected_tract'][-4:]}", True
    else:
        disp, lbl, is_s = master_df, "Area Average", False

    def get_val(col):
        if col not in master_df.columns: return 0.0
        return float(disp[col]) if is_s else float(disp[col].mean())

    st.subheader(f"📈 {lbl} Profile")
    
    # THE 7 INDICATOR GRID
    # We use a nested set of columns to ensure uniform size
    g1, g2, g3 = st.columns(3)
    g1.metric("Population", f"{get_val('pop_total'):,.0f}")
    g2.metric("Median Income", f"${get_val('med_hh_income'):,.0f}")
    g3.metric("Poverty Rate", f"{get_val('poverty_rate'):.1f}%")

    st.write("---")
    g4, g5, g6, g7 = st.columns(4)
    g4.metric("Unemployment", f"{get_val('unemp_rate'):.1f}%")
    g5.metric("Student Pop.", f"{get_val('age_18_24_pct'):.1f}%")
    g6.metric("HS Grad+", f"{get_val('hs_plus_pct_25plus'):.1f}%")
    g7.metric("College Grad+", f"{get_val('ba_plus_pct_25plus'):.1f}%")
    
    # Submission Form
    st.divider()
    st.subheader("📝 New Recommendation")
    all_geoids = sorted(master_df['GEOID'].unique().tolist())
    def_idx = all_geoids.index(st.session_state["selected_tract"]) if st.session_state["selected_tract"] in all_geoids else 0
    
    with st.form("sub_form", clear_on_submit=True):
        geoid = st.selectbox("Selected GEOID", options=all_geoids, index=def_idx)
        cat = st.selectbox("Category", ["Housing", "Infrastructure", "Commercial", "Other"])
        notes = st.text_area("Justification", height=80)
        if st.form_submit_button("Record Entry"):
            match = master_df.loc[master_df['GEOID'] == geoid, 'Is_Eligible']
            elig_label = "Eligible" if (not match.empty and match.values[0] == 1) else "Ineligible"
            new_row = pd.DataFrame([{"Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"), "User": st.session_state["username"], "GEOID": geoid, "Category": cat, "Justification": notes, "Is_Eligible": elig_label}])
            old_data = conn.read(worksheet="Sheet1", ttl=0)
            conn.update(worksheet="Sheet1", data=pd.concat([old_data, new_row], ignore_index=True))
            st.success("Recommendation Saved!")
            st.session_state["selected_tract"] = None
            st.rerun()

# --- 7. ACTIVITY LOG ---
st.divider()
st.subheader("📋 Recent Activity")
try:
    all_recs = conn.read(worksheet="Sheet1", ttl=0)
    user_view = all_recs if st.session_state["role"].lower() == "admin" else all_recs[all_recs['User'] == st.session_state['username']]
    st.dataframe(user_view, use_container_width=True, hide_index=True)
except:
    st.write("No activity recorded yet.")