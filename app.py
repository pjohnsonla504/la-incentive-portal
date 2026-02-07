import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import numpy as np
from math import radians, cos, sin, asin, sqrt
from streamlit_gsheets import GSheetsConnection

# --- 1. AUTHENTICATION ---
def check_password():
    def password_entered():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            users_df = conn.read(ttl="5m")
            users_df.columns = users_df.columns.str.strip().str.lower()
            entered_user = st.session_state["username"].strip()
            entered_pass = str(st.session_state["password"]).strip()
            if entered_user in users_df['username'].astype(str).values:
                user_row = users_df[users_df['username'].astype(str) == entered_user]
                if str(user_row['password'].values[0]).strip() == entered_pass:
                    st.session_state["password_correct"] = True
                    return
            st.session_state["password_correct"] = False
        except Exception as e:
            st.error(f"Auth Error: {e}")

    if "password_correct" not in st.session_state:
        st.title("Louisiana OZ 2.0 Portal")
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.button("Log In", on_click=password_entered)
        return False
    return True

if check_password():

    # --- 2. STYLING ---
    st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
        html, body, [class*="stApp"] { font-family: 'Inter', sans-serif; background-color: #0b0f19; color: #ffffff; }
        .content-section { padding: 60px 0; border-bottom: 1px solid #1e293b; width: 100%; }
        .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; letter-spacing: 0.1em; }
        .section-title { font-size: 2.5rem; font-weight: 900; margin-bottom: 20px; }
        .hero-title { font-family: 'Playfair Display', serif; font-size: 4rem; font-weight: 900; line-height: 1.1; color: #f8fafc; }
        .hero-subtitle { font-size: 0.95rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 30px; }
        .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 8px; height: 100%; }
        .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
        .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
        .anchor-pill { display: inline-block; padding: 6px 12px; border-radius: 4px; font-size: 0.75rem; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
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
        # Source GeoJSON
        url_geo = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
        try:
            r = requests.get(url_geo, timeout=10)
            geojson = r.json()
        except:
            return None, None, None, {}

        # CSV Load with encoding fix
        def read_csv_safe(f):
            try: return pd.read_csv(f, encoding='utf-8')
            except: return pd.read_csv(f, encoding='latin1')

        master = read_csv_safe("Opportunity Zones 2.0 - Master Data File.csv")
        anchors = read_csv_safe("la_anchors.csv")
        
        # Clean FIPS - crucial for ValueError prevention
        master['geoid_str'] = master['11-digit FIP'].astype(str).str.split('.').str[0].str.zfill(11)
        
        # Tracks highlighted green are only those eligible for the Opportunity Zone 2.0
        elig_col = 'Opportunity Zones Insiders Eligibilty'
        master['map_color'] = master[elig_col].apply(lambda x: 1 if str(x).strip().lower() in ['eligible', 'yes', '1'] else 0)

        centers = {}
        for feature in geojson['features']:
            geoid = feature['properties'].get('GEOID', feature['id'])
            geom = feature['geometry']
            coords = np.array(geom['coordinates'][0] if geom['type'] == 'Polygon' else geom['coordinates'][0][0])
            centers[str(geoid)] = [np.mean(coords[:, 0]), np.mean(coords[:, 1])]
            
        return geojson, master, anchors, centers

    gj, master_df, anchors_df, tract_centers = load_assets()

    # --- NARRATIVE SECTIONS 1, 2, 3 ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 1</div><div class='hero-subtitle'>Strategic Investment</div><div class='hero-title'>Louisiana Opportunity Zone 2.0</div></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 2</div><div class='section-title'>The Framework</div>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown("<div class='benefit-card'><h3>30% Rural Step-Up</h3><p>Enhanced basis step-up for Qualified Rural Opportunity Funds.</p></div>", unsafe_allow_html=True)
    with c2: st.markdown("<div class='benefit-card'><h3>Deferral</h3><p>Rolling deferral of original capital gains through 2031.</p></div>", unsafe_allow_html=True)
    with c3: st.markdown("<div class='benefit-card'><h3>Exclusion</h3><p>Permanent exclusion of gains on new investment appreciation.</p></div>", unsafe_allow_html=True)
    
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 3</div><div class='section-title'>Use Cases</div>", unsafe_allow_html=True)
    u1, u2 = st.columns(2)
    with u1: st.markdown("<div class='benefit-card'><h4>Healthcare Infrastructure</h4><p>Targeting rural medical anchors.</p></div>", unsafe_allow_html=True)
    with u2: st.markdown("<div class='benefit-card'><h4>Industrial Reuse</h4><p>Repurposing port-adjacent tracts.</p></div>", unsafe_allow_html=True)

    # --- SECTION 4: MAP ---
    st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Interactive Tract Analysis</div>", unsafe_allow_html=True)
    
    if gj is not None:
        m_col, p_col = st.columns([7, 3])
        with m_col:
            # Detect GeoJSON ID key dynamically
            id_key = "properties.GEOID" if "GEOID" in gj['features'][0]['properties'] else "id"
            
            fig = px.choropleth_mapbox(
                master_df, geojson=gj, locations="geoid_str", featureidkey=id_key,
                color="map_color", color_discrete_map={1: "#4ade80", 0: "rgba(30,41,59,0.4)"},
                mapbox_style="carto-darkmatter", zoom=6, center={"lat": 31.0, "lon": -91.8},
                opacity=0.6
            )
            fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', showlegend=False, height=700)
            selection = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

        with p_col:
            current_id = "22071001700"
            if selection and selection.get("selection", {}).get("points"):
                current_id = str(selection["selection"]["points"][0]["location"])
            
            row = master_df[master_df["geoid_str"] == current_id]
            if not row.empty:
                d = row.iloc[0]
                st.markdown(f"<h3>Tract {current_id}</h3><p style='color:#4ade80; font-weight:800;'>{d.get('Parish', 'Louisiana').upper()}</p>", unsafe_allow_html=True)
                
                # Metrics from Opportunity Zones Master File
                m1, m2 = st.columns(2)
                with m1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{d.get('Estimate!!Percent below poverty level!!Population for whom poverty status is determined', 'N/A')}%</div><div class='metric-label'>Poverty</div></div>", unsafe_allow_html=True)
                with m2: st.markdown(f"<div class='metric-card'><div class='metric-value'>{'YES' if d['map_color']==1 else 'NO'}</div><div class='metric-label'>Eligible</div></div>", unsafe_allow_html=True)

                if not anchors_df.empty and current_id in tract_centers:
                    t_lon, t_lat = tract_centers[current_id]
                    anchors_df['dist'] = anchors_df.apply(lambda r: haversine(t_lon, t_lat, r['Lon'], r['Lat']), axis=1)
                    st.write("---")
                    st.caption("NEAREST ANCHORS")
                    for _, a in anchors_df.sort_values('dist').head(5).iterrows():
                        st.markdown(f"<div class='anchor-pill'>📍 {a['Name']} ({a['dist']:.1f} mi)</div>", unsafe_allow_html=True)
    else:
        st.error("Error: Could not load map data.")

    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())