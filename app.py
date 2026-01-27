import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
import io

# --- 1. SETUP & AUTHENTICATION ---
st.set_page_config(page_title="LA Opportunity Zone Portal", layout="wide")

# Google Drive API Setup
def get_drive_service():
    # Uses the secrets you pasted into the Streamlit Dashboard
    info = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file"]
    )
    return build('drive', 'v3', credentials=creds)

# --- 2. DATA LOADING (Google Sheets) ---
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=600)
def load_data():
    # Read the data from your connected Google Sheet
    df = conn.read()
    return df

df = load_data()

# --- 3. SIDEBAR: PDF UPLOADER ---
st.sidebar.header("Submit Project Documentation")
uploaded_file = st.sidebar.file_uploader("Upload PDF Prospectus", type="pdf")

if uploaded_file is not None:
    if st.sidebar.button("Send to Google Drive"):
        try:
            service = get_drive_service()
            file_metadata = {
                'name': uploaded_file.name,
                'parents': ['1FHxg1WqoR3KwTpnJWLcSZTpoota-bKlk']  # Your Supporting Docs Folder
            }
            media = MediaIoBaseUpload(
                io.BytesIO(uploaded_file.getvalue()), 
                mimetype='application/pdf'
            )
            file = service.files().create(
                body=file_metadata, 
                media_body=media, 
                fields='id'
            ).execute()
            st.sidebar.success(f"File uploaded successfully! File ID: {file.get('id')}")
        except Exception as e:
            st.sidebar.error(f"Upload failed: {e}")

# --- 4. MAP & QUOTA LOGIC ---
st.title("Louisiana Incentive Portal: Opportunity Zones")

# Filter for Opportunity Zone 2.0 eligibility (Tracks highlighted green)
# NOTE: Ensure your sheet has a column named exactly 'OZ_2_0' with 'Yes' values
if 'OZ_2_0' in df.columns:
    oz_eligible = df[df['OZ_2_0'] == 'Yes']
    
    # Apply 25% Quota Logic: Only show 25% of the total eligible tracks
    display_count = max(1, len(oz_eligible) // 4)
    display_df = oz_eligible.sample(n=display_count)

    st.subheader(f"Showing {display_count} Exclusive Opportunity Zone 2.0 Tracks")

    # Plotly Map
    fig = px.scatter_mapbox(
        display_df,
        lat="Latitude",
        lon="Longitude",
        color_discrete_sequence=["#2ca02c"],  # Highlight Green for OZ 2.0
        zoom=6,
        height=600,
        hover_name="Tract_ID",
        hover_data=["Parish", "Population"]
    )

    fig.update_layout(mapbox_style="carto-positron")
    st.plotly_chart(fig, use_container_width=True)

    # --- 5. DATA TABLE ---
    st.write("### Detailed View of Available Tracks")
    st.dataframe(display_df)
else:
    st.error("Column 'OZ_2_0' not found in the Google Sheet. Please check your headers.")