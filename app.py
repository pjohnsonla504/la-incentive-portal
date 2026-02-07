import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. AMERICAN DYNAMISM DESIGN SYSTEM ---
st.set_page_config(page_title="Louisiana American Dynamism", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    /* Hero Section */
    .hero-title { font-size: 4rem; font-weight: 900; letter-spacing: -0.05em; line-height: 1; margin-bottom: 20px; color: #ffffff; }
    .hero-subtitle { font-size: 1.5rem; color: #4ade80; font-weight: 700; margin-bottom: 40px; text-transform: uppercase; }
    
    /* Content Blocks */
    .content-card { background: #161b28; border: 1px solid #2d3748; padding: 40px; border-radius: 0px; margin-bottom: 40px; }
    .section-header { font-size: 2rem; font-weight: 800; border-left: 4px solid #4ade80; padding-left: 20px; margin-bottom: 30px; text-transform: uppercase; }
    
    /* Metric Grid (Large & Bold) */
    .metric-container { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-top: 20px; }
    .metric-item { background: #1e2533; padding: 25px; border-bottom: 4px solid #4ade80; }
    .metric-label { font-size: 0.8rem; color: #94a3b8; font-weight: 700; text-transform: uppercase; margin-bottom: 10px; }
    .metric-value { font-size: 2rem; font-weight: 900; color: #ffffff; }

    /* Custom Indicators */
    .status-pill { display: inline-block; padding: 8px 20px; font-weight: 800; font-size: 0.9rem; border-radius: 50px; margin-right: 10px; }
    .active { background: #4ade80; color: #0b0f19; }
    .inactive { background: #2d3748; color: #94a3b8; }

    /* Map & Selection Overlay */
    .map-container { border: 1px solid #2d3748; margin-top: 40px; }
    
    /* Narrative Text */
    .narrative { font-size: 1.2rem; line-height: 1.8; color: #cbd5e1; max-width: 800px; margin-bottom: 40px; }
    
    /* Footer Style Progress */
    .progress-footer { position: fixed; bottom: 0; left: 0; width: 100%; background: #0b0f19; border-top: 1px solid #4ade80; padding: 15px 40px; z-index: 1000; display: flex; justify-content: space-between; align-items: center; }
    
    /* Global Overrides */
    [data-testid="stMetricValue"] { color: #ffffff !important; }
    [data-testid="stSidebar"] { display: none; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Precise Column Mapping
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

    # Standardize GEOID
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # Calculated Booleans
    df['pov_val'] = df[POV_COL].apply(clean) if POV_COL in df.columns else 0.0
    df['is_nmtc'] = df['pov_val'] >= 20.0
    df['is_deeply'] = (df['pov_val'] > 40.0) | (df[cols['unemp']].apply(clean) >= 10.5 if cols['unemp'] else False)

    # Eligibility Filter (Strictly Green Only)
    elig_col = find_col(['5-year', 'eligibility']) or find_col(['OZ', 'Eligible'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else df['is_nmtc']
    df['map_z'] = np.where(df['is_eligible'], 1, 0)

    # Assets & GeoJSON
    a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    centers = {}
    for feat in gj['features']:
        gid = str(feat['properties'].get('GEOID', '')).zfill(11)
        feat['properties']['GEOID_MATCH'] = gid
        if 'INTPTLAT' in feat['properties']:
            centers[gid] = {"lat": float(str(feat['properties']['INTPTLAT']).replace('+','')), "lon": float(str(feat['properties']['INTPTLON']).replace('+',''))}

    return df, gj, a, centers, cols

master_df, la_geojson, anchor_df, tract_centers, cols = load_data()

if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

# --- 3. THE LONG-SCROLL NARRATIVE ---

# HERO SECTION
st.markdown("""
    <div style='padding: 100px 0 60px 0;'>
        <div class='hero-subtitle'>American Dynamism</div>
        <div class='hero-title'>Louisiana<br>Opportunity Zones 2.0</div>
        <div class='narrative'>
            Building the future of the American South. We are identifying the census tracts 
            where technology, manufacturing, and local community resilience intersect to 
            drive national progress. This is the 150-site strategic portfolio for 2026.
        </div>
    </div>
""", unsafe_allow_html=True)

# SECTION 1: THE STRATEGIC MAP
st.markdown("<div class='section-header'>I. Selection Tool</div>", unsafe_allow_html=True)
st.markdown("<div class='best-practice'><b>Best Practice:</b> Target tracts with existing industrial anchors and poverty rates exceeding 25% for maximum federal incentive stacking.</div>", unsafe_allow_html=True)

fig = go.Figure(go.Choroplethmapbox(
    geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_z'],
    featureidkey="properties.GEOID_MATCH",
    colorscale=[[0, "rgba(255,255,255,0.02)"], [1, "#4ade80"]],
    showscale=False, marker_line_width=0.5, marker_line_color="#2d3748"
))
fig.update_layout(
    mapbox=dict(style="carto-darkmatter", center={"lat": 30.8, "lon": -91.8}, zoom=6.5),
    height=700, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
)
map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="dynamism_map")

if map_event and map_event.get("selection") and map_event["selection"]["points"]:
    st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)

# SECTION 2: TRACT ANALYSIS (CONDITIONAL)
sid = st.session_state.selected_tract
match = master_df[master_df['GEOID_KEY'] == sid]

if not match.empty:
    row = match.iloc[0]
    st.markdown(f"""
        <div class='content-card' id='analysis'>
            <div class='section-header'>II. Tract Profile: {sid}</div>
            <div style='margin-bottom:30px;'>
                <span class='status-pill active'>{'Urban' if 'metro' in str(row.get(cols['metro'])).lower() else 'Rural'}</span>
                <span class='status-pill {'active' if row['is_nmtc'] else 'inactive'}'>NMTC Eligible</span>
                <span class='status-pill {'active' if row['is_deeply'] else 'inactive'}'>Deeply Distressed</span>
            </div>
    """, unsafe_allow_html=True)

    # 8 METRIC GRID
    def f_val(c, is_p=True, is_d=False):
        v = row.get(c, 0)
        try:
            num = float(str(v).replace('%','').replace(',','').replace('$','').strip())
            return f"${num:,.0f}" if is_d else (f"{num:,.1f}%" if is_p else f"{num:,.0f}")
        except: return "N/A"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Poverty Rate", f_val(cols['pov'])); c2.metric("Unemployment", f_val(cols['unemp']))
    c3.metric("Labor Force", f_val(cols['labor'])); c4.metric("Median Home", f_val(cols['home'], False, True))
    
    c5, c6, c7, c8 = st.columns(4)
    c5.metric("HS Grad+", f_val(cols['hs'])); c6.metric("Bachelor Degree+", f_val(cols['bach']))
    try:
        bp = float(str(row.get(cols['base'])).replace(',',''))
        r65 = float(str(row.get("Population 65 years and over")).replace(',',''))
        c7.metric("Base Pop", f"{bp:,.0f}"); c8.metric("Elderly (65+)", f"{(r65/bp)*100:,.1f}%")
    except:
        c7.metric("Base Pop", "N/A"); c8.metric("65+ %", "N/A")

    # ANCHOR ANALYSIS
    st.markdown("<div class='section-label' style='margin-top:40px;'>Strategic Proximity (Nearest Anchors)</div>", unsafe_allow_html=True)
    t_pos = tract_centers.get(sid)
    if t_pos:
        a_df = anchor_df.copy()
        a_df['dist'] = a_df.apply(lambda x: np.sqrt((t_pos['lat']-x['lat'])**2 + (t_pos['lon']-x['lon'])**2) * 69, axis=1)
        t7 = a_df.sort_values('dist').head(7)
        st.table(t7[['name', 'type', 'dist']].rename(columns={'name': 'Anchor Asset', 'type': 'Category', 'dist': 'Miles'}))

    if st.button("EXECUTE NOMINATION", type="primary", use_container_width=True):
        st.session_state.recom_count += 1
        st.success(f"Tract {sid} has been added to the Strategic Portfolio.")

    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.markdown("""
        <div style='padding: 60px; text-align: center; border: 1px dashed #2d3748;'>
            <h3 style='color: #94a3b8;'>Select a Green Census Tract on the Map to Begin Analysis</h3>
        </div>
    """, unsafe_allow_html=True)

# FOOTER PROGRESS BAR
st.markdown(f"""
    <div class='progress-footer'>
        <div style='font-weight: 800; font-size: 0.9rem;'>PORTFOLIO PROGRESS: {st.session_state.recom_count} / 150</div>
        <div style='width: 60%; background: #1e2533; height: 10px; border-radius: 5px; margin: 0 20px;'>
            <div style='width: {min((st.session_state.recom_count/150)*100, 100)}%; background: #4ade80; height: 100%; border-radius: 5px;'></div>
        </div>
    </div>
""", unsafe_allow_html=True)