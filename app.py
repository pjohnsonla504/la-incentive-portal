import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. AUTHENTICATION FLOW ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 LA Incentive Portal Login")
    
    # Center the login form
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_input = st.text_input("Username")
            p_input = st.text_input("Password", type="password")
            submit = st.form_submit_button("Access Portal")
            
            if submit:
                try:
                    # Fetch credentials from the 'Users' tab
                    user_db = conn.read(worksheet="Users")
                    user_db.columns = [str(c).strip() for c in user_db.columns]
                    
                    # Validate match
                    match = user_db[(user_db['Username'] == u_input) & (user_db['Password'] == p_input)]
                    
                    if not match.empty:
                        st.session_state["authenticated"] = True
                        st.session_state["username"] = u_input
                        # Check if user is the Admin [cite: 2026-01-22]
                        st.session_state["is_admin"] = True if u_input == "Admin" else False
                        st.rerun()
                    else:
                        st.error("🚫 Invalid Username or Password. Please try again.")
                except Exception as e:
                    st.error("⚠️ Connection Error: Ensure you have a 'Users' tab in your Google Sheet.")
    st.stop()

# --- 3. LOGOUT & USER INFO (Sidebar) ---
st.sidebar.title("Navigation")
st.sidebar.info(f"👤 User: **{st.session_state['username']}**")
if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- 4. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    # Load Master CSV
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    # Load Map JSON
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# --- 5. DASHBOARD LAYOUT ---
st.title("📍 Louisiana Incentive Analysis Portal")

# Metrics row
m1, m2, m3 = st.columns(3)
m1.metric("Total Tracts", len(master_df))
m2.metric("OZ 2.0 Eligible", len(master_df[master_df['Is_Eligible'] == 1]))
# Pull Sheet1 to count total global recommendations
try:
    all_recs = conn.read(worksheet="Sheet1", ttl=0)
    m3.metric("Total Global Recs", len(all_recs))
except:
    all_recs = pd.DataFrame()
    m3.metric("Total Global Recs", 0)

# --- 6. INTERACTIVE MAP ---
st.divider()
st.subheader("Explore Opportunity Zones")

with st.expander("Regional Filtering Controls", expanded=True):
    r_col, e_col = st.columns(2)
    with r_col:
        region_list = ["All Regions"] + sorted(master_df['REDO_Region'].unique().tolist())
        sel_region = st.selectbox("Isolate REDO Region", options=region_list)
    with e_col:
        show_only_elig = st.toggle("Show Only Eligible Tracks (Green)")

# Filter the map data
map_df = master_df.copy()
if sel_region != "All Regions":
    map_df = map_df[map_df['REDO_Region'] == sel_region]
if show_only_elig:
    map_df = map_df[map_df['Is_Eligible'] == 1]

# Render Plotly Map
fig = px.choropleth_mapbox(
    map_df,
    geojson=la_geojson,
    locations="GEOID",
    featureidkey="properties.GEOID",
    color="Is_Eligible",
    # 1=Green, 0=Gray [cite: 2026-01-22]
    color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
    mapbox_style="carto-positron",
    zoom=6,
    center={"lat": 31.0, "lon": -91.8},
    opacity=0.5,
    hover_data=["GEOID", "Parish", "REDO_Region"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
st.plotly_chart(fig, use_container_width=True)

# --- 7. SUBMISSION FORM ---
st.divider()
st.subheader("Submit Recommendation")
with st.form("submission_form", clear_on_submit=True):
    geoid_choice = st.selectbox("Select Tract GEOID", options=sorted(master_df['GEOID'].unique()))
    category = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    notes = st.text_area("Justification / Strategic Value")
    
    if st.form_submit_button("Submit to Registry"):
        # Match eligibility from master
        status_match = master_df.loc[master_df['GEOID'] == geoid_choice, 'Is_Eligible']
        final_elig = "Eligible" if (not status_match.empty and status_match.values[0] == 1) else "Ineligible"
        
        # Build new row
        submission = pd.DataFrame([{
            "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "User": st.session_state["username"],
            "GEOID": geoid_choice,
            "Category": category,
            "Justification": notes,
            "Is_Eligible": final_elig
        }])
        
        # Append to Sheet1
        current_data = conn.read(worksheet="Sheet1", ttl=0)
        updated_sheet = pd.concat([current_data, submission], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_sheet)
        
        st.success(f"Success! {st.session_state['username']}, your entry has been saved.")
        st.balloons()

# --- 8. ACTIVITY LOG (Personalized) ---
st.divider()
st.subheader("Your Recent Activity")

if not all_recs.empty:
    all_recs.columns = [str(c).strip() for c in all_recs.columns]
    
    if st.session_state["is_admin"]:
        st.info("Showing **All User Submissions** (Admin Mode)")
        st.dataframe(all_recs, use_container_width=True, hide_index=True)
    else:
        # User only sees their own work [cite: 2026-01-22]
        user_view = all_recs[all_recs['User'] == st.session_state['username']]
        if user_view.empty:
            st.write("You haven't submitted any recommendations yet.")
        else:
            st.dataframe(user_view, use_container_width=True, hide_index=True)
else:
    st.write("The registry is currently empty.")