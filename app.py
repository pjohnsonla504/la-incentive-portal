import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")

st.title("📍 LA Tract Recommendation Portal")
st.markdown("Select a Census Tract to provide a justification for inclusion.")

# 2. Establish Google Sheets Connection
# This uses the [connections.gsheets] section from your Streamlit Secrets
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Load your reference data (Tracts and OZ Status)
# ttl=600 means it will refresh the list every 10 minutes
@st.cache_data(ttl=600)
def load_data():
    # This reads the list of tracts from your Sheet1
    return conn.read(worksheet="Sheet1") 

# Load the data into a dataframe
try:
    df = load_data()
except Exception as e:
    st.error("Could not load data from Google Sheets. Please check your Secrets and Permissions.")
    st.stop()

# 4. Highlight Logic (Opportunity Zone 2.0 = Green)
# Per instructions: Tracks highlighted green are only those eligible for OZ 2.0
def highlight_oz(row):
    if str(row['OZ_Status']).strip() == "Opportunity Zone 2.0":
        return ['background-color: #d4edda'] * len(row)
    return [''] * len(row)

# 5. Display the Interactive Table
st.subheader("Target Census Tracts")
st.markdown("Tracks highlighted in **green** are eligible for **Opportunity Zone 2.0**.")

if not df.empty:
    st.dataframe(
        df.style.apply(highlight_oz, axis=1),
        use_container_width=True,
        hide_index=True
    )
else:
    st.warning("The spreadsheet appears to be empty.")

# 6. Recommendation Form
st.divider()
st.subheader("Submit a Recommendation")

with st.form("recommendation_form", clear_on_submit=True):
    # Ensure 'Tract' matches the column header in your Google Sheet
    selected_tract = st.selectbox("Select Tract ID", options=df['Tract'].unique() if 'Tract' in df.columns else [])
    proj_cat = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    justification = st.text_area("Justification / Notes")
    
    submit_btn = st.form_submit_button("Submit to Google Sheets")

    if submit_btn:
        if not justification:
            st.warning("Please provide a justification before submitting.")
        else:
            try:
                # 1. Read current data to find the next empty row
                # ttl=0 ensures we aren't looking at a cached/old version
                current_data = conn.read(worksheet="Sheet1", ttl=0)
                
                # 2. Prepare the new row
                new_row = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    "Tract": selected_tract,
                    "Category": proj_cat,
                    "Justification": justification
                }])
                
                # 3. Combine existing data with the new entry
                updated_df = pd.concat([current_data, new_row], ignore_index=True)
                
                # 4. Push back to Google Sheets
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success(f"✅ Recommendation for Tract {selected_tract} successfully recorded!")
                st.balloons()
            except Exception as e:
                st.error(f"Error submitting to Google Sheets: {e}")
                st.info("Ensure your Service Account email is added as an 'Editor' on the Google Sheet.")

st.sidebar.info("Opportunity Zone 2.0 tracks are highlighted green in the table.")
