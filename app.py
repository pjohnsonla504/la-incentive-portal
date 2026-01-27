import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import io
from datetime import datetime

# --- 1. SETUP & AUTHENTICATION ---
st.set_page_config(page_title="LA OZ Recommendation Portal", layout="wide")

# Google Drive API Setup
def get_drive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build('drive', 'v3', credentials=creds)

# --- 2. DATA LOADING (Hybrid Model) ---
@st.cache_data
def load_csv_data():
    # Loads static rules from your GitHub repository
    return pd.read_csv("tract_data_final.csv")

profile_df = load_csv_data()

# Connect to the Google Sheet for logging recommendations
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk/edit#gid=0"
SUPPORTING_DOCS_FOLDER_ID = "1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk"

# --- 3. SIDEBAR: RECOMMENDATION FORM ---
st.sidebar.header("Submit Recommendation")

with st.sidebar.form("recommendation_form", clear_on_submit=True):
    # User selects GEOID from the CSV data
    rec_geoid = st.selectbox("Select GEOID", options=profile_df['GEOID'].unique())
    category = st.selectbox("Category", ["Housing", "Industrial", "Commercial", "Mixed-Use"])
    user_name = st.text_input("User (Name/Email)")
    justification = st.text_area("Justification")
    uploaded_file = st.file_uploader("Upload Supporting PDF", type="pdf")
    
    submit_button = st.form_submit_button("Submit Recommendation")

if submit_button:
    if rec_geoid and justification and user_name:
        try:
            # Step 1: Upload PDF to the 'Supporting Docs' folder
            file_link = "No Document"
            if uploaded_file:
                service = get_drive_service()
                file_metadata = {
                    'name': f"REC_{rec_geoid}_{uploaded_file.name}",
                    'parents': [SUPPORTING_DOCS_FOLDER_ID] 
                }
                media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype='application/pdf')
                drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                file_link = f"https://drive.google.com/file/d/{drive_file.get('id')}/view"

            # Step 2: Extract Eligibility from CSV (The fix for line 64)
            elig_status = profile_df.loc[profile_df['GEOID'] == rec_geoid, 'Is_Eligible'].values[0]
            
            # Step 3: Prepare data matching your Sheet headers: Date,GEOID,Category,Justification,Is_Eligible,User,Document
            new_row = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "GEOID": rec_geoid,
                "Category": category,
                "Justification": justification,
                "Is_Eligible": elig_status,
                "User": user_name,
                "Document": file_link
            }])
            
            # Step 4: Write to Google Sheet
            conn.create(spreadsheet=SHEET_URL, data=new_row)
            st.sidebar.success("✅ Submission Successful!")
            
        except Exception as e:
            st.sidebar.error(f"Error during submission: {e}")
    else:
        st.sidebar.warning("All text fields must be filled out.")

# --- 4. MAP & QUOTA LOGIC ---
st.title("📍 LA Opportunity Zone 2.0")

# Opportunity Zone 2.0 tracks are those highlighted green (Is_Eligible = 1)
oz_eligible = profile_df[profile_df['Is_Eligible'] == 1]
quota_count = max(1, int(len(oz_eligible) * 0.25))
display_df = oz_eligible.sample(n=quota_count)

st.subheader(f"Displaying {quota_count} Priority OZ 2.0 Tracks")

fig = px.scatter_mapbox(
    display_df,
    lat="lat", 
    lon="lon", 
    color_discrete_sequence=["#28a745"], # Green highlighting
    zoom=6, height=600,
    hover_name="GEOID",
    hover_data=["Parish", "pop_total"]
)
fig.update_layout(mapbox_style="carto-positron")
st.plotly_chart(fig, use_container_width=True)