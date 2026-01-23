import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# Initialize session states
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

# --- 3. DATA LOADING & CLEANING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    
    # Standardize GEOID
    if 'GEOID' in master.columns:
        master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # --- DATA SANITIZER: Convert strings to numbers for metrics ---
    cols_to_fix = ['poverty_rate', 'unemp_rate', 'med_hh_income']
    for col in cols_to_fix:
        if col in master.columns:
            # Remove $, %, and commas, then convert to numeric
            master[col] = pd.to_numeric(
                master[col].astype(str).replace(r'[\$,%]', '', regex=True), 
                errors='coerce'
            ).fillna(0)
    
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

# --- 5. SIDEBAR ---
st.sidebar.title("Navigation")
st.sidebar.info(f"👤 **{st.session_state['username']}**\n📍 Scope: {st.session_state['a_val']}")
if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.session_state["selected_tract"] = None
    st.rerun()

# --- 6. TOP METRICS & ECONOMIC INDICATORS ---
st.title(f"📍 {st.session_state['a_val']} Analysis Portal")

left_col, right_col = st.columns(2)

with left_col:
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

with right_col:
    st.subheader("Economic Snapshot")
    # Determine if we are looking at 1 tract or an average of the area
    if st.session_state["selected_tract"] and st.session_state["selected_tract"] in master_df['GEOID'].values:
        display_data = master_df[master_df['GEOID'] == st.session_state["selected_tract"]].iloc[0]
        label = f"Tract {st.session_state['selected_tract'][-4:]}"
        is_single = True
    else:
        display_data = master_df
        label = "Area Avg"
        is_single = False

    e1, e2, e3 = st.columns(3)

    def get_val(col):
        if is_single:
            return float(display_data[col])
        return float(display_data[col].mean())

    e1.metric(f"{label} Poverty", f"{get_val('poverty_rate'):.1f}%")
    e2.metric(f"{label} Unemp.", f"{get_val('unemp_rate'):.1f}%")
    e3.metric(f"{label} Income", f"${get_val('med_hh_income'):,.0f}")

# --- 7. MAP & FILTERS ---
st.divider()
with st.expander("Map Filters & Search", expanded=False):
    f1, f2 = st.columns(2)
    with f1:
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Isolate Specific Parish", options=p_list)
    with f2:
        only_elig = st.toggle("Highlight Only Eligible Tracks (Green)")

map_df = master_df.copy()
# Dynamic Centering Logic
if sel_parish != "All Authorized Parishes":
    map_df = map_df[map_df['Parish'] == sel_parish]
    zoom_lvl, center_coords = 9.5, {"lat": map_df['lat'].mean(), "lon": map_df['lon'].mean()}
elif st.session_state["role"].lower() != "admin":
    zoom_lvl, center_coords = 7.5, {"lat": map_df['lat'].mean(), "lon": map_df['lon'].mean()}
else:
    zoom_lvl, center_coords = 6.0, {"lat": 31.0, "lon": -91.8}

if only_elig:
    map_df = map_df[map_df['Is_Eligible'] == 1]

fig = px.choropleth_mapbox(
    map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
    color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
    mapbox_style="carto-positron", zoom=zoom_lvl, center=center_coords,
    opacity=0.6, hover_data=["GEOID", "Parish", "med_hh_income"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')

selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
    st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

# --- 8. SUBMISSION FORM ---
st.divider()
st.subheader("Submit Recommendation")

all_geoids = sorted(master_df['GEOID'].unique().tolist())
default_index = 0
if st.session_state["selected_tract"] in all_geoids:
    default_index = all_geoids.index(st.session_state["selected_tract"])

with st.form("sub_form", clear_on_submit=True):
    geoid = st.selectbox("Tract GEOID", options=all_geoids, index=default_index)
    cat = st.selectbox("Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    notes = st.text_area("Justification")
    
    if st.form_submit_button("Record Recommendation"):
        match = master_df.loc[master_df['GEOID'] == geoid, 'Is_Eligible']
        elig_label = "Eligible" if (not match.empty and match.values[0] == 1) else "Ineligible"
        
        new_row = pd.DataFrame([{
            "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "User": st.session_state["username"],
            "GEOID": geoid,
            "Category": cat,
            "Justification": notes,
            "Is_Eligible": elig_label
        }])
        
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
else:
    st.write("No activity recorded yet.")