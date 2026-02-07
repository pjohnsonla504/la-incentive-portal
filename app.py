import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM: a16z EDITORIAL + VIEWPORT OPTIMIZATION ---
st.set_page_config(page_title="Louisiana American Dynamism", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    /* Hero & Narrative Sections */
    .hero-title { font-family: 'Playfair Display', serif; font-size: 3.5rem; font-weight: 900; line-height: 1; margin-bottom: 15px; }
    .hero-subtitle { font-size: 0.9rem; color: #4ade80; font-weight: 800; letter-spacing: 0.15em; text-transform: uppercase; margin-bottom: 30px; }
    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; max-width: 1100px; margin: 0 auto; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    .narrative-text { font-size: 1rem; line-height: 1.6; color: #94a3b8; margin-bottom: 20px; }
    
    /* Section 4: Compact Portal Styles */
    .portal-container { padding: 20px; background: #0b0f19; border-top: 2px solid #1e293b; }
    .metric-card { background: #161b28; padding: 10px; border: 1px solid #2d3748; border-radius: 4px; }
    .metric-label { font-size: 0.6rem; color: #4ade80; font-weight: 800; text-transform: uppercase; margin-bottom: 2px; }
    .metric-value { font-size: 1.15rem; font-weight: 900; color: #ffffff; }

    /* Indicator Pills */
    .indicator-pill { display: inline-block; padding: 3px 10px; border-radius: 4px; font-weight: 800; font-size: 0.65rem; margin-right: 4px; border: 1px solid #2d3748; }
    .active { background: #4ade80; color: #0b0f19; border-color: #4ade80; }
    .inactive { color: #475569; }

    /* Progress Footer */
    .progress-footer { position: fixed; bottom: 0; left: 0; width: 100%; background: #0b0f19; border-top: 1px solid #4ade80; padding: 10px 40px; z-index: 1000; display: flex; align-items: center; justify-content: space-between; }
    
    /* Tables */
    .stTable { font-size: 0.7rem !important; margin-top: -10px; }
    thead tr th { background-color: #161b28 !important; color: #4ade80 !important; font-size: 0.6rem !important; padding: 4px !important; }
    tbody tr td { padding: 4px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    BASE_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
    def find_col(keywords):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keywords): return col
        return None

    cols = {
        "unemp": find_col(['unemployment', 'rate']),
        "metro": find_col(['metro', 'status']),
        "hs": find_col(['hs', 'degree']) or find_col(['high', 'school']),
        "bach": find_col(['bachelor']),
        "labor": find_col(['labor', 'force']),
        "home": find_col(['median', 'home', 'value']),
        "pov": POV_COL, "base": BASE_COL
    }

    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    df['pov_val'] = df[POV_COL].apply(clean)
    df['is_nmtc'] = df['pov_val'] >= 20.0
    df['is_deeply'] = (df['pov_val'] > 40.0) | (df[cols['unemp']].apply(clean) >= 10.5 if cols['unemp'] else False)

    # Tracks highlighted green are only those eligible for Opportunity Zone 2.0.
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else df['is_nmtc']
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

    a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {str(feat['properties'].get('GEOID')).zfill(11): {"lat": float(str(feat['properties'].get('INTPTLAT')).replace('+','')), "lon": float(str(feat['properties'].get('INTPTLON')).replace('+',''))} for feat in gj['features'] if 'INTPTLAT' in feat['properties']}
    for feat in gj['features']: feat['properties']['GEOID_MATCH'] = str(feat['properties'].get('GEOID')).zfill(11)

    return df, gj, a, centers, cols

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

# --- SECTION 1 & 2 (ABRIDGED FOR DISPLAY) ---
st.markdown("<div class='content-section' style='padding-top:80px;'><div class='hero-subtitle'>American Dynamism</div><div class='hero-title'>Louisiana<br>Strategic Portals</div></div>", unsafe_allow_html=True)

# SECTION 3: LEVERAGING STRATEGIC DATA
st.markdown("""
<div class='content-section'>
    <div class='section-num'>03</div>
    <div class='section-title'>Leveraging Strategic Data</div>
    <div class='narrative-text'>
        To use this resource effectively, look for <b>statistical friction</b>: tracts where low socio-economic metrics are adjacent to high-value infrastructure assets. 
    </div>
""")

# Instruction Visual
st.markdown("""
<div style='background: #161b28; padding: 20px; border-radius: 8px; border: 1px solid #2d3748; margin-bottom: 25px;'>
    <div style='display: grid; grid-template-columns: 1fr 0.2fr 1fr; align-items: center; text-align: center;'>
        <div>
            <div class='metric-label'>Step 1: Metric Identification</div>
            <p style='font-size:0.85rem; color:#cbd5e1;'>Filter for <b>'Deeply Distressed'</b> status (<40% Poverty or high unemployment) to unlock maximum federal grant stacking.</p>
        </div>
        <div style='font-size: 2rem; color: #4ade80;'>+</div>
        <div>
            <div class='metric-label'>Step 2: Proximity Analysis</div>
            <p style='font-size:0.85rem; color:#cbd5e1;'>Identify <b>Anchor Assets</b> (Ports, Universities, or Rail) within 5 miles to ensure industrial viability.</p>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)



st.markdown("</div>", unsafe_allow_html=True)

# SECTION 4: THE INTERACTIVE PORTAL
st.markdown("<div class='portal-container'><div class='section-num'>04</div><div class='section-title'>Strategic Selection Tool</div>", unsafe_allow_html=True)

map_col, profile_col = st.columns([0.42, 0.58], gap="small")

with map_col:
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(255,255,255,0.02)"], [1, "#4ade80"]],
        showscale=False, marker_line_width=0.2, marker_line_color="#2d3748"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-darkmatter", center={"lat": 30.8, "lon": -91.8}, zoom=5.8),
        height=520, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="selection_map")
    
    sid = None
    if map_event and map_event.get("selection") and map_event["selection"]["points"]:
        sid = str(map_event["selection"]["points"][0]["location"]).zfill(11)

with profile_col:
    if sid:
        row = master_df[master_df['GEOID_KEY'] == sid].iloc[0]
        st.markdown(f"<div style='margin-bottom:8px;'><h4 style='margin:0; font-size:1.2rem;'>TRACT {sid} <span style='color:#4ade80; font-size:0.8rem; margin-left:10px;'>{row.get('Parish', '').upper()}</span></h4></div>", unsafe_allow_html=True)
        
        m_val = str(row.get(cols['metro'], '')).lower()
        st.markdown(f"""
            <div style='margin-bottom:10px;'>
                <span class='indicator-pill {'active' if 'metro' in m_val else 'inactive'}'>URBAN</span>
                <span class='indicator-pill {'active' if 'rural' in m_val else 'inactive'}'>RURAL</span>
                <span class='indicator-pill {'active' if row['is_nmtc'] else 'inactive'}'>NMTC</span>
                <span class='indicator-pill {'active' if row['is_deeply'] else 'inactive'}'>DEEP DISTRESS</span>
            </div>
        """, unsafe_allow_html=True)

        # 8 METRIC CARDS (4x2 COMPACT)
        def f_val(c, is_p=True, is_d=False):
            v = row.get(c, 0)
            try:
                num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
                return f"${num:,.0f}" if is_d else (f"{num:,.1f}%" if is_p else f"{num:,.0f}")
            except: return "N/A"

        r1, r2, r3, r4 = st.columns(4)
        r1.markdown(f"<div class='metric-card'><div class='metric-label'>Poverty</div><div class='metric-value'>{f_val(cols['pov'])}</div></div>", unsafe_allow_html=True)
        r2.markdown(f"<div class='metric-card'><div class='metric-label'>Unempl.</div><div class='metric-value'>{f_val(cols['unemp'])}</div></div>", unsafe_allow_html=True)
        r3.markdown(f"<div class='metric-card'><div class='metric-label'>Labor</div><div class='metric-value'>{f_val(cols['labor'])}</div></div>", unsafe_allow_html=True)
        r4.markdown(f"<div class='metric-card'><div class='metric-label'>Home Val</div><div class='metric-value'>{f_val(cols['home'], False, True)}</div></div>", unsafe_allow_html=True)
        
        r5, r6, r7, r8 = st.columns(4)
        r5.markdown(f"<div class='metric-card' style='margin-top:5px;'><div class='metric-label'>HS Grad+</div><div class='metric-value'>{f_val(cols['hs'])}</div></div>", unsafe_allow_html=True)
        r6.markdown(f"<div class='metric-card' style='margin-top:5px;'><div class='metric-label'>Bach+</div><div class='metric-value'>{f_val(cols['bach'])}</div></div>", unsafe_allow_html=True)
        try:
            bp = float(str(row.get(cols['base'])).replace(',',''))
            r65 = float(str(row.get("Population 65 years and over")).replace(',',''))
            r7.markdown(f"<div class='metric-card' style='margin-top:5px;'><div class='metric-label'>Total Pop</div><div class='metric-value'>{bp:,.0f}</div></div>", unsafe_allow_html=True)
            r8.markdown(f"<div class='metric-card' style='margin-top:5px;'><div class='metric-label'>65+ %</div><div class='metric-value'>{(r65/bp)*100:,.1f}%</div></div>", unsafe_allow_html=True)
        except:
            r7.markdown(f"<div class='metric-card' style='margin-top:5px;'><div class='metric-label'>Pop</div><div class='metric-value'>N/A</div></div>", unsafe_allow_html=True)
            r8.markdown(f"<div class='metric-card' style='margin-top:5px;'><div class='metric-label'>65+</div><div class='metric-value'>N/A</div></div>", unsafe_allow_html=True)

        # ANCHORS
        t_pos = tract_centers.get(sid)
        if t_pos:
            a_df = anchor_df.copy()
            a_df['dist'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
            t7 = a_df.sort_values('dist').head(4) # Shrunk to 4 for viewport
            st.table(t7[['name', 'type', 'dist']].rename(columns={'name': 'Anchor', 'type': 'Type', 'dist': 'Mi'}))

        if st.button("NOMINATE FOR 2026 PORTFOLIO", type="primary", use_container_width=True):
            st.session_state.recom_count += 1
            st.rerun()
    else:
        st.markdown("<div style='padding: 140px 20px; text-align: center; background: #161b28; border: 1px dashed #2d3748; color:#64748b;'>Select a green tract to load profile</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

# FOOTER PROGRESS
st.markdown(f"""
    <div class='progress-footer'>
        <div style='font-weight: 800; font-size: 0.75rem;'>2026 TARGET PORTFOLIO PROGRESS: {st.session_state.recom_count} / 150</div>
        <div style='flex-grow: 1; height: 3px; background: #1e293b; margin: 0 30px; position: relative;'>
            <div style='width: {min((st.session_state.recom_count/150)*100, 100)}%; background: #4ade80; height: 100%;'></div>
        </div>
    </div>
""", unsafe_allow_html=True)