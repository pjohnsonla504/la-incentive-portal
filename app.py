import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. AUTHENTICATION & LOCKING LOGIC ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 LA Incentive Portal Login")
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        with st.form("login_form"):
            u_input = st.text_input("Username")
            p_input = st.text_input("Password", type="password")
            if st.form_submit_button("Access Portal"):
                # Load the Users tab
                user_db = conn.read(worksheet="Users")
                user_db.columns = [str(c).strip() for c in user_db.columns]
                
                # Verify Username and Password
                match = user_db[(user_db['Username'] == u_input) & (user_db['Password'] == p_input)]
                
                if not match.empty:
                    user_data = match.iloc[0]
                    st.session_state["authenticated"] = True
                    st.session_state["username"] = u_input
                    st.session_state["role"] = user_data['Role']
                    st.session_state["a_type"] = user_data['Assigned_Type']
                    st.session_state["a_val"] = user_data['Assigned_Value']
                    st.rerun()
                else:
                    st.error("Invalid credentials. Please check your spelling.")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    # Clean GEOIDs for mapping
    master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# --- 4. TERRITORY ISOLATION (Security Layer) ---
# This ensures users can't see or submit for areas outside their assignment
if st.session_state["role"] != "Admin":
    target_col = st.session_state["a_type"] # REDO_Region or Parish
    target_val = st.session_state["a_val"]  # e.g., Bayou or Orleans
    
    # Filter the master list immediately
    master_df = master_df[master_df[target_col] == target_val]

# --- 5. SIDEBAR & NAVIGATION ---
st.sidebar.title("Navigation")
st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
st.sidebar.info(f"📍 Authorized Scope: \n**{st.session_state['a_val']}** ({st.session_state['a_type']})")

if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.rerun()

# --- 6. MAIN DASHBOARD ---
st.title(f"📍 {st.session_state['a_val']} Analysis Portal")
st.caption(f"Welcome back, {st.session_state['username']}. Data is isolated to your assigned territory.")

# Metrics
m1, m2, m3 = st.columns(3)
m1.metric("Local Tracts", len(master_df))
m2.metric("OZ 2.0 Eligible", len(master_df[master_df['Is_Eligible'] == 1]))
try:
    all_recs = conn.read(worksheet="Sheet1", ttl=0)
    user_count = len(all_recs[all_recs['User'] == st.session_state['username']])
    m3.metric("Your Submissions", user_count)
except:
    m3.metric("Your Submissions", 0)

# --- 7. MAP & PARISH FILTER ---
st.divider()
with st.expander("Map Controls", expanded=True):
    f1, f2 = st.columns(2)
    with f1:
        # If Parish user, this list only contains their parish. If Region, it contains all parishes in region.
        p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
        sel_parish = st.selectbox("Isolate Specific Parish", options=p_list)
    with f2:
        only_elig = st.toggle("Highlight Only Eligible (Green)")

map_df = master_df.copy()
if sel_parish != "All Authorized Parishes":
    map_df = map_df[map_df['Parish'] == sel_parish]
if only_elig:
    map_df = map_df[map_df['Is_Eligible'] == 1]

# Dynamic Zoom: Map centers on the average coordinates of the isolated data
fig = px.choropleth_mapbox(
    map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
    color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
    mapbox_style="carto-positron", 
    zoom=7 if st.session_state["role"] != "Admin" else 6,
    center={"lat": 31.0, "lon": -92.0}, # Centered on LA
    opacity=0.6, hover_data=["GEOID", "Parish", "REDO_Region"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False)
st.plotly_chart(fig, use_container_width=True)

# --- 8. SUBMISSION FORM ---
st.divider()
st.subheader("Submit Recommendation")
with st.form("sub_form", clear_on_submit=True):
    # This dropdown ONLY shows GEOIDs from the user's isolated territory
    geoid = st.selectbox("Select Tract GEOID", options=sorted(master_df['GEOID'].unique()))
    cat = st.selectbox("Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    notes = st.text_area("Justification / Strategic Value")
    
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
        
        # Read and Append to Sheet1
        try:
            old_data = conn.read(worksheet="Sheet1", ttl=0)
            updated_df = pd.concat([old_data, new_row], ignore_index=True)
            conn.update(worksheet="Sheet1", data=updated_df)
            st.success("Recommendation recorded successfully!")
            st.balloons()
        except Exception as e:
            st.error(f"Error saving to Google Sheets: {e}")

# --- 9. PERSONALIZED LOG ---
st.divider()
st.subheader("Recent Activity Log")
if st.session_state["role"] == "Admin":
    st.info("💡 Admin Access: Viewing all global submissions.")
    st.dataframe(all_recs, use_container_width=True, hide_index=True)
else:
    # Filter log to only show the user's own submissions
    user_log = all_recs[all_recs['User'] == st.session_state['username']]
    st.dataframe(user_log, use_container_width=True, hide_index=True)