import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection

# 1. Page Configuration
st.set_page_config(page_title="LA Incentive Portal", layout="wide")

st.title("📍 LA Tract Recommendation Portal")
st.markdown("Select a Census Tract to provide a justification for inclusion.")

# 2. Establish Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# 3. Load data with error handling
@st.cache_data(ttl=60) # Refreshes every minute
def load_data():
    return conn.read(worksheet="Sheet1") 

try:
    df = load_data()
    
    # Check if necessary columns exist
    required_columns = ['Tract', 'OZ_Status']
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        st.error(f"Missing columns in Google Sheet: {', '.join(missing)}")
        st.info("Please ensure Row 1 includes: Date, Tract, Category, Justification, OZ_Status")
        st.stop()

except Exception as e:
    st.error(f"Could not load data: {e}")
    st.stop()

# 4. Highlight Logic (Opportunity Zone 2.0 = Green)
def highlight_oz(row):
    # Case-insensitive check for the status
    status = str(row.get('OZ_Status', '')).strip()
    if status == "Opportunity Zone 2.0":
        return ['background-color: #d4edda'] * len(row)
    return [''] * len(row)

# 5. Display the Table
st.subheader("Target Census Tracts")
st.dataframe(
    df.style.apply(highlight_oz, axis=1),
    use_container_width=True,
    hide_index=True
)

# 6. Submission Form
st.divider()
st.subheader("Submit a Recommendation")

with st.form("recommendation_form", clear_on_submit=True):
    selected_tract = st.selectbox("Select Tract ID", options=df['Tract'].unique())
    proj_cat = st.selectbox("Project Category", ["Housing", "Infrastructure", "Commercial", "Other"])
    justification = st.text_area("Justification / Notes")
    
    submit_btn = st.form_submit_button("Submit to Google Sheets")

    if submit_btn:
        if not justification:
            st.warning("Please enter a justification.")
        else:
            try:
                # Get fresh data to append to
                current_data = conn.read(worksheet="Sheet1", ttl=0)
                
                new_row = pd.DataFrame([{
                    "Date": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
                    "Tract": selected_tract,
                    "Category": proj_cat,
                    "Justification": justification,
                    "OZ_Status": df.loc[df['Tract'] == selected_tract, 'OZ_Status'].values[0]
                }])
                
                updated_df = pd.concat([current_data, new_row], ignore_index=True)
                conn.update(worksheet="Sheet1", data=updated_df)
                
                st.success("✅ Success! Your recommendation has been saved.")
                st.balloons()
            except Exception as e:
                st.error(f"Submission failed: {e}")