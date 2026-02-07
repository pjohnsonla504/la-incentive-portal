import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import json
import numpy as np

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="OZ 2.0 | Strategic Portal", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f172a; color: #f1f5f9; }
    .profile-header { background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #4ade80; margin-bottom: 20px; }
    .header-item { display: inline-block; margin-right: 30px; }
    .header-label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase; font-weight: 700; display: block; }
    .header-value { color: #ffffff; font-size: 1.1rem; font-weight: 800; }
    .stProgress > div > div > div > div { background-color: #4ade80; }
    [data-testid="stMetricValue"] { color: #4ade80 !important; font-size: 1.5rem !important; font-weight: 800; }
    .stMetric { background-color: #1e293b; border-radius: 8px; border: 1px solid #334155; padding: 12px; }
    .indicator-box { border-radius: 8px; padding: 12px; text-align: center; margin-bottom: 10px; border: 2px solid #475569; height: 110px; display: flex; flex-direction: column; justify-content: center; }
    .status-yes { background-color: rgba(74, 222, 128, 0.2); border-color: #4ade80 !important; }
    .status-no { background-color: rgba(30, 41, 59, 0.5); border-color: #334155 !important; opacity: 0.6; }
    .indicator-label { font-size: 0.7rem; color: #ffffff; text-transform: uppercase; font-weight: 800; line-height: 1.1; }
    .indicator-value { font-size: 1.1rem; font-weight: 900; color: #ffffff; margin-top: 5px; }
    .section-label { color: #94a3b8; font-size: 0.85rem; font-weight: 800; margin-top: 15px; border-bottom: 1px solid #334155; padding-bottom: 5px; text-transform: uppercase; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA UTILITIES ---
@st.cache_data(ttl=60)
def load_data():
    df = pd.read_csv("Opportunity Zones 2.0 - Master Data File.csv")
    df.columns = df.columns.str.strip()
    
    # Precise Column Mapping
    POV_COL = "Estimate!!Percent below poverty level!!Population for whom poverty status is determined"
    BASE_POP_COL = "Estimate!!Total!!Population for whom poverty status is determined"
    
    # Fuzzy finder for others
    def find_col(keywords):
        for col in df.columns:
            if all(k.lower() in col.lower() for k in keywords): return col
        return None

    unemp_col = find_col(['unemployment', 'rate'])
    mfi_col = find_col(['median', 'family', 'income']) or find_col(['median', 'household', 'income'])
    
    # GEOID Logic
    f_match = [c for c in df.columns if 'FIP' in c or 'digit' in c]
    g_col = f_match[0] if f_match else df.columns[1]
    df['GEOID_KEY'] = df[g_col].astype(str).apply(lambda x: x.split('.')[0]).str.zfill(11)
    
    def clean_num(val):
        try: return float(str(val).replace('%','').replace(',','').replace('$','').strip())
        except: return 0.0

    # Calculated Metrics
    df['pov_rate'] = df[POV_COL].apply(clean_num) if POV_COL in df.columns else 0.0
    df['unemp_rate'] = df[unemp_col].apply(clean_num) if unemp_col else 0.0
    df['mfi_val'] = df[mfi_col].apply(clean_num) if mfi_col else 999999.0

    # Deeply Distressed Criteria (Version 61 logic)
    # 1. Poverty > 40%
    # 2. Unemployment >= 10.5% (2.5x proxy)
    # 3. MFI <= 40% of state median (~26,000)
    df['is_nmtc_deeply'] = (df['pov_rate'] > 40.0) | (df['unemp_rate'] >= 10.5) | (df['mfi_val'] <= 26000)
    df['is_nmtc_eligible'] = df['pov_rate'] >= 20.0

    # Track Highlighted Green
    elig_col = find_col(['5-year', 'eligibility'])
    df['is_eligible'] = df[elig_col].astype(str).str.lower().str.strip().isin(['yes', 'eligible', 'y']) if elig_col else df['is_nmtc_eligible']
    df['map_status'] = np.where(df['is_eligible'], 1, 0)

    try: a = pd.read_csv("la_anchors.csv")
    except: a = pd.read_csv("la_anchors.csv", encoding='cp1252')
    a.columns = a.columns.str.strip().str.lower()
    with open("tl_2025_22_tract.json") as f: gj = json.load(f)
    
    return df, gj, a, POV_COL, BASE_POP_COL

master_df, la_geojson, anchor_df, POV_NAME, BASE_POP_NAME = load_data()

# --- 3. INTERFACE ---
if "recom_count" not in st.session_state: st.session_state.recom_count = 0
if "selected_tract" not in st.session_state: st.session_state.selected_tract = None

col_map, col_side = st.columns([0.55, 0.45])

with col_map:
    fig = go.Figure(go.Choroplethmapbox(
        geojson=la_geojson, locations=master_df['GEOID_KEY'], z=master_df['map_status'],
        featureidkey="properties.GEOID_MATCH",
        colorscale=[[0, "rgba(200,200,200,0.1)"], [1, "rgba(74, 222, 128, 0.65)"]],
        showscale=False, marker_line_width=1, marker_line_color="#1e293b"
    ))
    fig.update_layout(
        mapbox=dict(style="carto-positron", center={"lat": 31.0, "lon": -91.8}, zoom=6.2),
        height=1020, margin={"r":0,"t":0,"l":0,"b":0}, clickmode='event+select'
    )
    map_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="oz_map_v61")
    if map_event and "selection" in map_event and map_event["selection"]["points"]:
        st.session_state.selected_tract = str(map_event["selection"]["points"][0]["location"]).zfill(11)
        st.rerun()

with col_side:
    st.markdown("<p style='font-weight:700; margin-bottom:5px;'>NOMINATION TARGET PROGRESS (Goal: 150)</p>", unsafe_allow_html=True)
    st.progress(min(st.session_state.recom_count / 150, 1.0))
    
    sid = st.session_state.selected_tract
    match = master_df[master_df['GEOID_KEY'] == sid]
    
    if not match.empty:
        row = match.iloc[0]
        st.markdown(f"""
            <div class='profile-header'>
                <div class='header-item'><span class='header-label'>Tract ID</span><span class='header-value'>{sid}</span></div>
                <div class='header-item'><span class='header-label'>Parish</span><span class='header-value'>{row.get('Parish')}</span></div>
                <div class='header-item'><span class='header-label'>Region</span><span class='header-value'>{row.get('Region', 'Louisiana')}</span></div>
            </div>
        """, unsafe_allow_html=True)
        
        # INDICATORS
        st.markdown("<div class='section-label'>Qualification Indicators</div>", unsafe_allow_html=True)
        i1, i2 = st.columns(2)
        with i1:
            st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc_eligible'] else 'status-no'}'><div class='indicator-label'>NMTC Eligible<br>(Poverty ≥ 20%)</div><div class='indicator-value'>{'QUALIFIED' if row['is_nmtc_eligible'] else 'NO'}</div></div>", unsafe_allow_html=True)
        with i2:
            st.markdown(f"<div class='indicator-box {'status-yes' if row['is_nmtc_deeply'] else 'status-no'}'><div class='indicator-label'>Deeply Distressed<br>(Pov > 40%, Unemp 2.5x, or MFI ≤ 40%)</div><div class='indicator-value'>{'QUALIFIED' if row['is_nmtc_deeply'] else 'NO'}</div></div>", unsafe_allow_html=True)

        # HUMAN CAPITAL
        st.markdown("<div class='section-label'>Human Capital & Demographics</div>", unsafe_allow_html=True)
        h1, h2, h3, h4 = st.columns(4)
        try:
            base_pop = float(str(row.get(BASE_POP_NAME)).replace(",",""))
            raw_65 = float(str(row.get("Population 65 years and over")).replace(",",""))
            pct_65 = (raw_65 / base_pop) * 100 if base_pop > 0 else 0
            h1.metric("Base Pop", f"{base_pop:,.0f}")
            h2.metric("Elderly %", f"{pct_65:,.1f}%")
        except:
            h1.metric("Base Pop", "N/A"); h2.metric("Elderly %", "N/A")
            
        h3.metric("Poverty Rate", f"{row['pov_rate']}%")
        h4.metric("Unemployment", f"{row['unemp_rate']}%")

        # NOMINATION
        st.divider()
        st.subheader("STRATEGIC NOMINATION")
        cat = st.selectbox("Category", ["Energy Transition", "Cybersecurity", "Critical Mfg", "Defense Tech"])
        just = st.text_area("Justification (Required)")
        if st.button("EXECUTE NOMINATION", type="primary"):
            if just:
                st.session_state.recom_count += 1
                st.success("Nominated.")
                st.rerun()
            else: st.warning("Please provide justification.")
    else:
        st.info("Select a highlighted tract to view strategic profile.")