import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import numpy as np
import ssl
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

# --- 0. INITIAL CONFIG ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

# Initialize session state keys
if "session_recs" not in st.session_state:
    st.session_state["session_recs"] = []
if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = None 
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. PERSISTENCE & DELETE ENGINE ---
def load_user_recs(username):
    """Retrieves saved recommendations from Google Sheets for the specific user."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        recs_df = conn.read(worksheet="Recommendations", ttl=0) 
        user_recs = recs_df[recs_df['username'].astype(str) == str(username)].to_dict('records')
        return user_recs
    except Exception:
        return []

def save_rec_to_cloud(rec_entry):
    """Appends a single recommendation to the Google Sheet."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        rec_entry['username'] = st.session_state["username"]
        existing_df = conn.read(worksheet="Recommendations", ttl=0)
        
        is_duplicate = ((existing_df['username'].astype(str) == str(rec_entry['username'])) & 
                        (existing_df['Tract'].astype(str) == str(rec_entry['Tract']))).any()
        
        if not is_duplicate:
            new_df = pd.concat([existing_df, pd.DataFrame([rec_entry])], ignore_index=True)
            conn.update(worksheet="Recommendations", data=new_df)
            return True
        return False
    except Exception as e:
        st.error(f"Cloud Save Failed: {e}")
        return False

def delete_rec_from_cloud(tract_id):
    """Removes a specific tract for the current user from the Google Sheet."""
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        existing_df = conn.read(worksheet="Recommendations", ttl=0)
        
        # Filter: Keep rows that DON'T match this user + this tract
        new_df = existing_df[~((existing_df['username'].astype(str) == str(st.session_state["username"])) & 
                               (existing_df['Tract'].astype(str) == str(tract_id)))]
        
        conn.update(worksheet="Recommendations", data=new_df)
        # Update local state immediately
        st.session_state["session_recs"] = [r for r in st.session_state["session_recs"] if str(r['Tract']) != str(tract_id)]
        return True
    except Exception as e:
        st.error(f"Cloud Deletion Failed: {e}")
        return False

# --- 2. AUTHENTICATION & LOGOUT ---
def logout():
    st.session_state["password_correct"] = False
    st.session_state["username"] = ""
    st.session_state["session_recs"] = []
    st.session_state["active_tract"] = None
    st.rerun()

def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username_input"].strip()
            p = str(st.session_state["password_input"]).strip()
            
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    st.session_state["username"] = u
                    st.session_state["session_recs"] = load_user_recs(u)
                    return
            st.session_state["password_correct"] = False
            st.error("Invalid username or password")
        except Exception as e:
            st.error(f"Error connecting to database: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("""<style>
            .stApp { background-color: #0b0f19 !important; font-family: 'Inter', sans-serif; }
            div[data-testid="stVerticalBlock"] > div:has(input) {
                background-color: #111827; padding: 40px; border-radius: 15px; border: 1px solid #1e293b;
            }
            input { background-color: #0b0f19 !important; color: white !important; }
            button[kind="primary"] { background-color: #4ade80 !important; color: #0b0f19 !important; font-weight: 900 !important; }
        </style>""", unsafe_allow_html=True)

        _, col_mid, _ = st.columns([1, 0.8, 1])
        with col_mid:
            st.markdown("<h1 style='color: white; text-align:center;'>OZ 2.0 Portal</h1>", unsafe_allow_html=True)
            st.text_input("Username", key="username_input")
            st.text_input("Password", type="password", key="password_input")
            st.button("Sign In", on_click=password_entered, use_container_width=True)
        return False
    return True

if check_password():
    # --- 3. UI STYLING & NAVIGATION ---
    st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background: rgba(11, 15, 25, 0.95); border-bottom: 1px solid #1e293b; padding: 15px; z-index: 9999; display: flex; justify-content: center; gap: 20px; }
        .nav-link { color: white !important; text-decoration: none; font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .main .block-container { padding-top: 80px !important; }
        
        /* High Contrast Download Button */
        div.stDownloadButton > button {
            background-color: #ffffff !important;
            color: #0b0f19 !important;
            border: 2px solid #4ade80 !important;
            font-weight: 900 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.1em !important;
            width: 100% !important;
            margin-top: 20px !important;
            padding: 15px !important;
        }
        div.stDownloadButton > button:hover {
            background-color: #4ade80 !important;
            color: #0b0f19 !important;
        }

        .benefit-card { background: #111827; padding: 20px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.2rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; }
    </style>
    <div class="nav-container">
        <a class="nav-link" href="#section-1">Overview</a>
        <a class="nav-link" href="#section-2">Benefits</a>
        <a class="nav-link" href="#section-3">Strategy</a>
        <a class="nav-link" href="#section-5">Mapping</a>
        <a class="nav-link" href="#report-section">My Report</a>
    </div>""", unsafe_allow_html=True)

    with st.sidebar:
        st.write(f"Active Account: **{st.session_state['username']}**")
        if st.button("Log Out"): logout()

    # --- 4. DATA ENGINE & ASSETS ---
    def safe_float(val):
        try:
            if pd.isna(val) or val == '' or val == 'N/A': return 0.0
            return float(str(val).replace('$', '').replace(',', '').replace('%', '').strip())
        except: return 0.0

    @st.cache_data(ttl=3600)
    def load_assets():
        master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        # Assuming Opportunity Zone 2.0 logic from saved information
        master['Eligible'] = master['Opportunity Zones Insiders Eligibilty'].apply(lambda x: 'Yes' if str(x).lower() in ['yes', 'eligible'] else 'No')
        return master

    master_df = load_assets()

    # --- SECTION 1: OVERVIEW ---
    st.markdown("<div id='section-1'></div>", unsafe_allow_html=True)
    st.title("Louisiana Opportunity Zones 2.0 Portal")
    st.markdown("A strategic tool for analyzing Census Tracts under the OZ 2.0 legislative framework.")

    # --- SECTION 2: BENEFITS ---
    st.markdown("<div id='section-2'></div><br><h3>Benefit Framework</h3>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1: st.markdown("<div class='benefit-card'><h4>Capital Deferral</h4><p>Reinvested gains are deferred until 2026 or asset sale.</p></div>", unsafe_allow_html=True)
    with b2: st.markdown("<div class='benefit-card'><h4>Basis Step-Up</h4><p>10-15% reduction in original tax liability over long holds.</p></div>", unsafe_allow_html=True)
    with b3: st.markdown("<div class='benefit-card'><h4>Full Exclusion</h4><p>Zero tax on appreciation for investments held over 10 years.</p></div>", unsafe_allow_html=True)

    # --- SECTION 3: STRATEGY ---
    st.markdown("<div id='section-3'></div><br><h3>Strategic Advocacy</h3>", unsafe_allow_html=True)
    st.write("Focusing on tracts that intersect high-speed broadband, university anchors, and rural connectivity.")

    # --- SECTION 5: MAPPING & ANALYSIS ---
    st.markdown("<div id='section-5'></div><br><h3>Census Tract Analysis</h3>", unsafe_allow_html=True)
    
    col_parish, col_tract = st.columns(2)
    with col_parish:
        parish = st.selectbox("Filter by Parish", ["All"] + sorted(master_df['Parish'].unique().tolist()))
    
    filtered_df = master_df if parish == "All" else master_df[master_df['Parish'] == parish]
    
    with col_tract:
        sel_geoid = st.selectbox("Select Tract GEOID", [""] + sorted(filtered_df['geoid_str'].tolist()))

    if sel_geoid:
        row = master_df[master_df["geoid_str"] == sel_geoid].iloc[0]
        
        # Metric Cards
        m1, m2, m3 = st.columns(3)
        m1.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Eligible', 'N/A')}</div><div class='metric-label'>OZ 2.0 Eligible</div></div>", unsafe_allow_html=True)

        # Recommendation Inputs
        rec_cat = st.selectbox("Opportunity Category", ["Affordable Housing", "Infrastructure", "Tech/Venture", "Medical/Healthcare"])
        just = st.text_area("Investment Justification", placeholder="Describe why this tract is a strategic fit...")
        
        if st.button("Save Recommendation to My Account", type="primary"):
            entry = {
                "Tract": sel_geoid,
                "Parish": row.get('Parish', 'N/A'),
                "Category": rec_cat,
                "Justification": just,
                "Population": int(safe_float(row.get('Estimate!!Total!!Population for whom poverty status is determined', 0))),
                "Poverty": f"{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0))}%",
                "MFI": f"${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}",
                "Broadband": f"{safe_float(row.get('Broadband Internet (%)', 0))}%"
            }
            if save_rec_to_cloud(entry):
                st.session_state["session_recs"].append(entry)
                st.success(f"Tract {sel_geoid} successfully saved to cloud.")
                st.rerun()

    # --- SECTION 6: THE REPORT & MANAGEMENT ---
    st.markdown("<div id='report-section'></div><br>", unsafe_allow_html=True)
    st.divider()
    st.header(f"Strategy Report: {st.session_state['username']}")
    
    if st.session_state["session_recs"]:
        # High Contrast Download Button
        report_df = pd.DataFrame(st.session_state["session_recs"])
        csv_data = report_df[[c for c in report_df.columns if c != 'username']].to_csv(index=False)
        
        st.download_button(
            label="📥 Download Strategy Report (CSV)",
            data=csv_data,
            file_name=f"OZ_Analysis_{st.session_state['username']}.csv",
            mime="text/csv",
        )

        st.subheader("Saved Recommendations")
        for rec in st.session_state["session_recs"]:
            with st.container():
                c_data, c_act = st.columns([0.85, 0.15])
                with c_data:
                    st.markdown(f"**Tract {rec['Tract']}** ({rec['Parish']}) — *{rec['Category']}*")
                    st.caption(f"Justification: {rec['Justification']}")
                with c_act:
                    if st.button("Delete", key=f"del_{rec['Tract']}", use_container_width=True):
                        if delete_rec_from_cloud(rec['Tract']):
                            st.toast(f"Removed Tract {rec['Tract']}")
                            st.rerun()
                st.markdown("<hr style='border: 0.1px solid #1e293b;'>", unsafe_allow_html=True)
    else:
        st.info("No recommendations saved yet. Select a Census Tract above to begin your report.")