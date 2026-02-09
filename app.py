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
import streamlit.components.v1 as components
from datetime import datetime

# --- 0. INITIAL CONFIG & STATE INITIALIZATION ---
st.set_page_config(page_title="Louisiana Opportunity Zones 2.0 Portal", layout="wide")

if "active_tract" not in st.session_state:
    st.session_state["active_tract"] = "22071001700" 
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None
if "password_correct" not in st.session_state:
    st.session_state["password_correct"] = False

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except:
    pass

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(worksheet="Users", ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            u = st.session_state["username"].strip()
            p = str(st.session_state["password"]).strip()
            if u in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == u]
                if str(user_row['password'].values[0]).strip() == p:
                    st.session_state["password_correct"] = True
                    st.session_state["current_user"] = u 
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if not st.session_state["password_correct"]:
        st.markdown("<div style='text-align:center; padding:50px;'><h1 style='color:white;'>Louisiana OZ 2.0 Login</h1></div>", unsafe_allow_html=True)
        _, col_mid, _ = st.columns([1, 1.2, 1])
        with col_mid:
            st.text_input("Username", key="username")
            st.text_input("Password", type="password", key="password")
            st.button("Secure Login", on_click=password_entered, use_container_width=True, type="primary")
        return False
    return True

if check_password():
    conn = st.connection("gsheets", type=GSheetsConnection)

    # --- 2. GLOBAL STYLING ---
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        
        .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 20px; }
        
        /* Fixed Size Benefit Cards for Sections 2, 3, 4 */
        .benefit-card { 
            background: #161b28; 
            padding: 25px; 
            border: 1px solid #2d3748; 
            border-radius: 8px; 
            min-height: 220px; 
            display: flex; 
            flex-direction: column; 
            transition: 0.3s;
        }
        .benefit-card:hover { border-color: #4ade80; }
        .benefit-card h3 { color: #f8fafc; font-size: 1.2rem; margin-bottom: 10px; }
        .benefit-card p { color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }

        .metric-card { background: #111827; padding: 8px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; height: 85px; display: flex; flex-direction: column; justify-content: center; margin-bottom: 8px;}
        .metric-value { font-size: 1.1rem; font-weight: 900; color: #4ade80; }
        .metric-label { font-size: 0.55rem; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.05em; margin-top: 3px; }
        
        /* Profile Header Layout */
        .tract-header-container { background: #111827; padding: 20px 25px; border-radius: 10px; border-top: 4px solid #4ade80; margin-bottom: 15px; }
        .header-parish { font-size: 1.8rem; font-weight: 900; color: #4ade80; text-transform: uppercase; margin-bottom: 5px; }
        .header-sub-row { display: flex; justify-content: space-between; border-top: 1px solid #1e293b; padding-top: 10px; }
        
        .stTextArea textarea { color: #ffffff !important; -webkit-text-fill-color: #ffffff !important; }
        </style>
        """, unsafe_allow_html=True)

    # --- 3. DATA ENGINE ---
    def haversine(lon1, lat1, lon2, lat2):
        lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
        dlon, dlat = lon2 - lon1, lat2 - lat1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        return 3956 * 2 * asin(sqrt(a))

    @st.cache_data(ttl=3600)
    def load_assets():
        geojson = None
        if os.path.exists("tl_2025_22_tract.json"):
            with open("tl_2025_22_tract.json", "r") as f: geojson = json.load(f)
        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')
        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        # Eligibility color filter (Green only for Yes/Eligible)
        master['Eligibility_Status'] = master['Opportunity Zones Insiders Eligibilty'].apply(
            lambda x: 'Eligible' if str(x).strip().lower() in ['eligible', 'yes', '1'] else 'Ineligible'
        )
        anchors = read_csv_safe("la_anchors.csv")
        centers = {}
        if geojson:
            for feature in geojson['features']:
                props = feature['properties']
                geoid = props.get('GEOID') or props.get('GEOID20')
                try:
                    coords = np.array(feature['geometry']['coordinates'][0]) if feature['geometry']['type'] == 'Polygon' else np.array(feature['geometry']['coordinates'][0][0])
                    centers[geoid] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
                except: continue
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    def create_la_map(df, geojson, height=600):
        fig = px.choropleth_mapbox(
            df, geojson=geojson, locations="geoid_str", 
            featureidkey="properties.GEOID" if "GEOID" in str(geojson) else "properties.GEOID20",
            color="Eligibility_Status", color_discrete_map={"Eligible": "#4ade80", "Ineligible": "#cbd5e1"},
            mapbox_style="carto-positron", zoom=6.2, center={"lat": 30.8, "lon": -91.8}, opacity=0.5
        )
        # ENHANCE LEGIBILITY: Pull Parish Labels to the top
        fig.update_traces(below='traces')
        fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=height, clickmode='event+select')
        return fig

    # --- SECTION 1: HERO ---
    st.markdown("<div style='padding:60px 0; text-align:center;'><h1 style='font-size:3.5rem; font-weight:900;'>Louisiana OZ 2.0</h1><p style='color:#4ade80; font-size:1.2rem; font-weight:700;'>STRATEGIC INVESTMENT PORTAL</p></div>", unsafe_allow_html=True)

    # --- SECTIONS 2, 3, 4: FRAMEWORK & BEST PRACTICES ---
    sections_content = [
        ("SECTION 2", "The OZ 2.0 Benefit Framework", [
            ("Capital Gain Deferral", "Defer taxes on original capital gains for 5 years."),
            ("Basis Step-Up", "Qualified taxpayer receives 10% basis step-up (30% if rural)."),
            ("Permanent Exclusion", "Zero federal capital gains tax on appreciation after 10 years.")
        ]),
        ("SECTION 3", "Census Tract Advocacy", [
            ("Geographically Disbursed", "Zones will be distributed throughout the state focusing on rural areas."),
            ("Distressed Communities", "Eligibility is dependent on the federal definition of a low-income community."),
            ("Project Ready", "Aligning recommendations with tracts likely to receive private investment.")
        ]),
        ("SECTION 4", "Best Practices", [
            ("Economic Innovation Group", "Proximity to ports and manufacturing hubs ensures long-term tenant demand."),
            ("Frost Brown Todd", "Utilizing local educational anchors to provide a skilled labor force."),
            ("American Policy Institute", "Stack incentives to de-risk projects for long-term growth.")
        ])
    ]

    for num, title, cards in sections_content:
        st.markdown(f"<div class='content-section'><div class='section-num'>{num}</div><div class='section-title'>{title}</div>", unsafe_allow_html=True)
        cols = st.columns(3)
        for i, (ct, ctx) in enumerate(cards):
            cols[i].markdown(f"<div class='benefit-card'><h3>{ct}</h3><p>{ctx}</p></div>", unsafe_allow_html=True)

    # --- SECTION 5: ASSET MAPPING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 5</div><div class='section-title'>Strategic Asset Mapping</div>", unsafe_allow_html=True)
    col5a, col5b = st.columns([0.6, 0.4])
    with col5a:
        fig5 = create_la_map(master_df, gj)
        sel5 = st.plotly_chart(fig5, use_container_width=True, on_select="rerun", key="map5")
        if sel5 and sel5.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel5["selection"]["points"][0]["location"])
    with col5b:
        st.markdown(f"**ANCHOR ASSETS NEAR {st.session_state['active_tract']}**")
        list_html = ""
        if st.session_state["active_tract"] in tract_centers:
            lon, lat = tract_centers[st.session_state["active_tract"]]
            anchors_df['dist'] = anchors_df.apply(lambda r: haversine(lon, lat, r['Lon'], r['Lat']), axis=1)
            for _, a in anchors_df.sort_values('dist').head(10).iterrows():
                list_html += f"<div style='background:#111827; padding:10px; margin-bottom:8px; border-radius:5px;'><b>{a['Name']}</b><br><span style='color:#4ade80; font-size:0.8rem;'>{a['Type']} • {a['dist']:.1f} mi</span></div>"
        components.html(f"<div style='height:500px; overflow-y:auto;'>{list_html}</div>", height=520)

    # --- SECTION 6: TRACT PROFILING ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 6</div><div class='section-title'>Tract Profiling & Recommendations</div>", unsafe_allow_html=True)
    col6a, col6b = st.columns([0.5, 0.5])
    with col6a:
        fig6 = create_la_map(master_df, gj, height=750)
        sel6 = st.plotly_chart(fig6, use_container_width=True, on_select="rerun", key="map6")
        if sel6 and sel6.get("selection", {}).get("points"): st.session_state["active_tract"] = str(sel6["selection"]["points"][0]["location"])
    with col6b:
        row = master_df[master_df["geoid_str"] == st.session_state["active_tract"]]
        if not row.empty:
            d = row.iloc[0]
            # Custom Mappings
            h_val = d.get('Median Home Value', 'N/A')
            p_65 = d.get('Population 65 years and over', '0')
            pov = float(d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 0))

            st.markdown(f"""
                <div class='tract-header-container'>
                    <div class='header-parish'>{str(d.get('Parish','')).upper()}</div>
                    <div class='header-sub-row'>
                        <div><div style='color:#94a3b8; font-size:0.7rem;'>TRACT</div><div style='font-weight:700;'>{st.session_state['active_tract']}</div></div>
                        <div style='text-align:right;'><div style='color:#94a3b8; font-size:0.7rem;'>REGION</div><div style='font-weight:700;'>{str(d.get('Region','')).upper()}</div></div>
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            # Metrics
            r1 = st.columns(3)
            r1[0].markdown(f"<div class='metric-card'><div class='metric-value'>{pov}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
            r1[1].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Unemployment Rate (%)','0')}%</div><div class='metric-label'>Unemployment</div></div>", unsafe_allow_html=True)
            r1[2].markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if pov > 20 else 'NO'}</div><div class='metric-label'>NMTC ELIGIBLE</div></div>", unsafe_allow_html=True)
            
            r2 = st.columns(3)
            r2[0].markdown(f"<div class='metric-card'><div class='metric-value'>{h_val}</div><div class='metric-label'>Median Home Value</div></div>", unsafe_allow_html=True)
            r2[1].markdown(f"<div class='metric-card'><div class='metric-value'>{p_65}</div><div class='metric-label'>Pop (65+)</div></div>", unsafe_allow_html=True)
            r2[2].markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Broadband Internet (%)','0')}%</div><div class='metric-label'>Broadband</div></div>", unsafe_allow_html=True)
            
            st.write("---")
            cat = st.selectbox("Category", ["Housing", "Industrial", "Commercial", "Tech"])
            just = st.text_area("Justification")
            if st.button("Submit Recommendation", type="primary", use_container_width=True):
                new_rec = pd.DataFrame([{"Date": datetime.now().strftime("%Y-%m-%d"), "GEOID": st.session_state["active_tract"], "Category": cat, "Justification": just, "User": st.session_state["current_user"]}])
                conn.create(worksheet="Sheet1", data=new_rec)
                st.success("Saved to Sheet1")
                st.rerun()

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())