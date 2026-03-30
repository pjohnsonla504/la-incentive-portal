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

# --- 1. PERSISTENCE ENGINE ---
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
    """Appends a single recommendation to the Google Sheet if it doesn't exist."""
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
                background-color: #111827; padding: 40px; border-radius: 15px;
                border: 1px solid #1e293b;
            }
            label { color: #94a3b8 !important; font-weight: 700; }
            input { background-color: #0b0f19 !important; color: white !important; border: 1px solid #2d3748 !important; }
            button[kind="primary"] { background-color: #4ade80 !important; color: #0b0f19 !important; font-weight: 900 !important; border: none !important; height: 3em !important; }
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
    # --- UI STYLING & NAV ---
    st.markdown("""<style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif !important; background-color: #0b0f19 !important; color: #ffffff; }
        .nav-container { position: fixed; top: 0; left: 0; width: 100%; background: rgba(11, 15, 25, 0.95); border-bottom: 1px solid #1e293b; padding: 15px; z-index: 9999; display: flex; justify-content: center; gap: 20px; }
        .nav-link { color: white !important; text-decoration: none; font-weight: 700; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.1em; }
        .main .block-container { padding-top: 80px !important; }
        .benefit-card { background: #111827; padding: 25px; border: 1px solid #2d3748; border-radius: 12px; height: 100%; }
        .metric-card { background: #111827; padding: 15px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.2rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.6rem; text-transform: uppercase; color: #94a3b8; }
    </style>
    <div class="nav-container">
        <a class="nav-link" href="#section-1">Overview</a>
        <a class="nav-link" href="#section-2">Benefits</a>
        <a class="nav-link" href="#section-3">Strategy</a>
        <a class="nav-link" href="#section-4">Best Practices</a>
        <a class="nav-link" href="#section-5">Mapping</a>
    </div>""", unsafe_allow_html=True)

    # Sidebar Logout
    with st.sidebar:
        st.write(f"Logged in: **{st.session_state['username']}**")
        if st.button("Log Out"): logout()

    # --- DATA ENGINE & HELPERS ---
    def safe_float(val):
        try:
            if pd.isna(val) or val == '' or val == 'N/A': return 0.0
            return float(str(val).replace('$', '').replace(',', '').replace('%', '').strip())
        except: return 0.0

    def safe_int(val): return int(safe_float(val))

    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 3956 * 2 * asin(sqrt(a))

    @st.cache_data(ttl=3600)
    def load_assets():
        gj = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: gj = json.load(f)
        
        master = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1', 'true'] else 'Ineligible'
        )
        
        anchors = pd.read_csv("la_anchors.csv")
        centers = {}
        if gj:
            for feature in gj['features']:
                geoid = feature['properties'].get('GEOID') or feature['properties'].get('GEOID20')
                try:
                    geom = feature['geometry']
                    pts = np.array(geom['coordinates'][0]) if geom['type'] == 'Polygon' else np.array(geom['coordinates'][0][0])
                    centers[geoid] = [np.mean(pts[:, 0]), np.mean(pts[:, 1])]
                except: continue
        return gj, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- SECTION 1: OVERVIEW ---
    st.markdown("<div id='section-1'></div>", unsafe_allow_html=True)
    st.title("Louisiana OZ 2.0 Portal")
    st.markdown("The Opportunity Zones Program is a federal capital gains tax incentive program designed to drive long-term investments to low-income communities.")

    # --- SECTION 2: BENEFITS ---
    st.markdown("<div id='section-2'></div><br><h3>The Benefit Framework</h3>", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1: st.markdown("<div class='benefit-card'><h4>Gain Deferral</h4><p>Defer taxes on capital gains reinvested in a QOF for up to five years.</p></div>", unsafe_allow_html=True)
    with b2: st.markdown("<div class='benefit-card'><h4>Basis Step-Up</h4><p>5-year hold grants 10% basis increase (Urban) or 30% (Rural).</p></div>", unsafe_allow_html=True)
    with b3: st.markdown("<div class='benefit-card'><h4>Gain Exclusion</h4><p>10-year hold permanently excludes new capital gains from tax.</p></div>", unsafe_allow_html=True)

    # --- SECTION 3: STRATEGY ---
    st.markdown("<div id='section-3'></div><br><h3>Strategic Advocacy</h3>", unsafe_allow_html=True)
    s1, s2, s3 = st.columns(3)
    with s1: st.markdown("<div class='benefit-card'><h4>Geo-Diversity</h4><p>Prioritizing rural areas with strong transportation access.</p></div>", unsafe_allow_html=True)
    with s2: st.markdown("<div class='benefit-card'><h4>Market Readiness</h4><p>Balancing community need with regulatory readiness.</p></div>", unsafe_allow_html=True)
    with s3: st.markdown("<div class='benefit-card'><h4>Anchor Proximity</h4><p>Focusing on tracts within 5 miles of hospitals and universities.</p></div>", unsafe_allow_html=True)

    # --- SECTION 4: BEST PRACTICES ---
    st.markdown("<div id='section-4'></div><br><h3>Best Practices</h3>", unsafe_allow_html=True)
    st.write("Alignment with EIG, Frost Brown Todd, and America First Policy Institute frameworks.")

    # --- SECTION 5: MAPPING & ANALYSIS ---
    st.markdown("<div id='section-5'></div><br><h3>Strategic Mapping</h3>", unsafe_allow_html=True)
    
    f1, f2 = st.columns(2)
    with f1: sel_parish = st.selectbox("Parish Filter", ["All"] + sorted(master_df['Parish'].unique().tolist()))
    filtered_df = master_df if sel_parish == "All" else master_df[master_df['Parish'] == sel_parish]
    
    with f2: sel_geoid = st.selectbox("Select Tract GEOID", [""] + sorted(filtered_df['geoid_str'].tolist()))
    
    if sel_geoid:
        st.session_state["active_tract"] = sel_geoid
        row = master_df[master_df["geoid_str"] == sel_geoid].iloc[0]
        
        # Demographics
        st.markdown(f"**Analysis for Tract: {sel_geoid} ({row['Parish']})**")
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
        m2.markdown(f"<div class='metric-card'><div class='metric-value'>${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}</div><div class='metric-label'>MFI</div></div>", unsafe_allow_html=True)
        m3.markdown(f"<div class='metric-card'><div class='metric-value'>{safe_float(row.get('Unemployment Rate (%)', 0)):.1f}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
        m4.markdown(f"<div class='metric-card'><div class='metric-value'>{row.get('Metro Status (Metropolitan/Rural)', 'N/A')}</div><div class='metric-label'>Metro Status</div></div>", unsafe_allow_html=True)

        # Analysis Inputs
        rec_cat = st.selectbox("Recommendation Category", ["Housing", "Business", "Tech", "Healthcare"])
        just = st.text_area("Strategic Justification")
        
        if st.button("Add to My Report", type="primary"):
            entry = {
                "Tract": sel_geoid, "Parish": row['Parish'], "Category": rec_cat, "Justification": just,
                "Population": safe_int(row.get('Estimate!!Total!!Population for whom poverty status is determined', 0)),
                "Poverty": f"{safe_float(row.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0)):.1f}%",
                "MFI": f"${safe_float(row.get('Estimate!!Median family income in the past 12 months (in 2024 inflation-adjusted dollars)', 0)):,.0f}",
                "Broadband": f"{safe_float(row.get('Broadband Internet (%)', 0)):.1f}%"
            }
            if save_rec_to_cloud(entry):
                st.session_state["session_recs"].append(entry)
                st.success("Tract saved to your permanent account!")
                st.rerun()
            else:
                st.warning("This tract is already in your report.")

    # --- SECTION 6: PERSISTENT REPORT ---
    st.divider()
    st.subheader(f"Saved Report for {st.session_state['username']}")
    if st.session_state["session_recs"]:
        rdf = pd.DataFrame(st.session_state["session_recs"])
        st.dataframe(rdf[[c for c in rdf.columns if c != 'username']], use_container_width=True)
        st.download_button("Download CSV", rdf.to_csv(index=False), f"OZ_Report_{st.session_state['username']}.csv")
    else:
        st.info("No saved data found for this account.")