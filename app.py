import streamlit as st
import pandas as pd
import plotly.express as px
import json
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. AUTHENTICATION ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False
if "selected_tract" not in st.session_state:
    st.session_state["selected_tract"] = None

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
                    st.session_state["role"] = user_data['Role']
                    st.session_state["a_type"] = user_data['Assigned_Type']
                    st.session_state["a_val"] = user_data['Assigned_Value']
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    st.stop()

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    master['GEOID'] = master['GEOID'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().str.zfill(11)
    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson

master_df, la_geojson = load_data()

# --- 4. TERRITORY ISOLATION ---
if st.session_state["role"] != "Admin":
    master_df = master_df[master_df[st.session_state["a_type"]] == st.session_state["a_val"]]

# --- 5. SIDEBAR ---
st.sidebar.title("Navigation")
st.sidebar.info(f"👤 **{st.session_state['username']}**\n📍 {st.session_state['a_val']}")
if st.sidebar.button("Log Out"):
    st.session_state["authenticated"] = False
    st.session_state["selected_tract"] = None
    st.rerun()

# --- 6. MAP WITH SELECTION LOGIC ---
st.title(f"📍 {st.session_state['a_val']} Analysis Portal")

with st.expander("Map Filters", expanded=True):
    p_list = ["All Authorized Parishes"] + sorted(master_df['Parish'].unique().tolist())
    sel_parish = st.selectbox("Isolate Specific Parish", options=p_list)
    only_elig = st.toggle("Highlight Only Eligible (Green)")

map_df = master_df.copy()
if sel_parish != "All Authorized Parishes":
    map_df = map_df[map_df['Parish'] == sel_parish]
if only_elig:
    map_df = map_df[map_df['Is_Eligible'] == 1]

fig = px.choropleth_mapbox(
    map_df, geojson=la_geojson, locations="GEOID", featureidkey="properties.GEOID",
    color="Is_Eligible", color_continuous_scale=[(0, "#6c757d"), (1, "#28a745")],
    mapbox_style="carto-positron", zoom=7, center={"lat": 31.0, "lon": -92.0},
    opacity=0.6, hover_data=["GEOID", "Parish"]
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, coloraxis_showscale=False, clickmode='event+select')

# This allows the app to "hear" when the map is clicked
selected_points = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

# Update the selected tract in session state based on map click
if selected_points and "selection" in selected_points and len(selected_points["selection"]["points"]) > 0:
    # Get the GEOID from the clicked point
    st.session_state["selected_tract"] = selected_points["selection"]["points"][0]["location"]

# --- 7. SUBMISSION FORM (Linked to Map) ---
st.divider()
st.subheader("Submit Recommendation")

# Logic to determine index of the selectbox based on map click
all_geoids = sorted(master_df['GEOID'].unique().tolist())
default_index = 0
if st.session_state["selected_tract"] in all_geoids:
    default_index = all_geoids.index(st.session_state["selected_tract"])

with st.form("sub_form", clear_on_submit=True):
    # Selectbox now defaults to whatever was clicked on the map
    geoid = st.selectbox("Select Tract GEOID", options=all_geoids, index=default_index)
    cat = st.selectbox("Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    notes = st.text_area("Justification")
    
    if st.form_submit_button("Submit"):
        match = master_df.loc[master_df['GEOID'] == geoid, 'Is_Eligible']
        elig = "Eligible" if (not match.empty and match.values[0] == 1) else "Ineligible"
        
        new_row = pd.DataFrame([{
            "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "User": st.session_state["username"],
            "GEOID": geoid,
            "Category": cat,
            "Justification": notes,
            "Is_Eligible": elig
        }])
        
        old_data = conn.read(worksheet="Sheet1", ttl=0)
        conn.update(worksheet="Sheet1", data=pd.concat([old_data, new_row], ignore_index=True))
        st.success(f"Recommendation for {geoid} saved!")
        st.session_state["selected_tract"] = None # Reset after submit
        st.balloons()

# --- 8. ACTIVITY LOG ---
st.divider()
try:
    all_recs = conn.read(worksheet="Sheet1", ttl=0)
    user_recs = all_recs if st.session_state["role"] == "Admin" else all_recs[all_recs['User'] == st.session_state['username']]
    st.dataframe(user_recs, use_container_width=True, hide_index=True)
except:
    st.write("No activity recorded.")