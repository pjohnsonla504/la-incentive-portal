import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import io
import json
from datetime import datetime

# --- 1. SETUP ---
st.set_page_config(page_title="LA OZ Recommendation Portal", layout="wide")

def get_drive_service():
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build('drive', 'v3', credentials=creds)

# --- 2. DATA LOADING ---
@st.cache_data
def load_data():
    # Load your CSV rules
    df = pd.read_csv("tract_data_final.csv")
    # Ensure GEOID is a string to match the JSON file
    df['GEOID'] = df['GEOID'].astype(str)
    
    # Load the Map GeoJSON file
    with open("tl_2025_22_tract.json") as f:
        la_map = json.load(f)
    return df, la_map

profile_df, la_geojson = load_data()

# Connections
conn = st.connection("gsheets", type=GSheetsConnection)
SHEET_URL = "https://docs.google.com/spreadsheets/d/1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk/edit#gid=0"
FOLDER_ID = "1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk"

# --- 3. SIDEBAR FORM ---
st.sidebar.header("Submit Recommendation")
with st.sidebar.form("recommendation_form", clear_on_submit=True):
    rec_geoid = st.selectbox("Select GEOID", options=profile_df['GEOID'].unique())
    category = st.selectbox("Category", ["Housing", "Industrial", "Commercial", "Mixed-Use"])
    user_name = st.text_input("User (Name/Email)")
    justification = st.text_area("Justification")
    uploaded_file = st.file_uploader("Upload Supporting PDF", type="pdf")
    submit_button = st.form_submit_button("Submit Recommendation")

if submit_button:
    if rec_geoid and justification and user_name:
        try:
            file_link = "No Document"
            if uploaded_file:
                service = get_drive_service()
                file_metadata = {'name': f"REC_{rec_geoid}_{uploaded_file.name}", 'parents': [FOLDER_ID]}
                media = MediaIoBaseUpload(io.BytesIO(uploaded_file.getvalue()), mimetype='application/pdf')
                drive_file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
                file_link = f"https://drive.google.com/file/d/{drive_file.get('id')}/view"

            elig_status = profile_df.loc[profile_df['GEOID'] == rec_geoid, 'Is_Eligible'].values[0]
            
            new_row = pd.DataFrame([{
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "GEOID": rec_geoid, "Category": category, "Justification": justification,
                "Is_Eligible": elig_status, "User": user_name, "Document": file_link
            }])
            
            conn.create(spreadsheet=SHEET_URL, data=new_row)
            st.sidebar.success("✅ Submission Successful!")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")

# --- 4. MAP (Fixed with Choropleth) ---
st.title("📍 LA Opportunity Zone 2.0")

# Filter for OZ 2.0 Eligibility based on your CSV Header 'Is_Eligible'
oz_eligible = profile_df[profile_df['Is_Eligible'] == 1]

# Apply 25% Quota Logic
quota_count = max(1, int(len(oz_eligible) * 0.25))
display_df = oz_eligible.sample(n=quota_count)

st.subheader(f"Displaying {quota_count} Priority OZ 2.0 Tracks")