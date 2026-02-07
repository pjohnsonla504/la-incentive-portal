import streamlit as st
import pandas as pd
import plotly.express as px
import json
import requests

# --- 1. DESIGN SYSTEM ---
st.set_page_config(page_title="Louisiana OZ 2.0 Portal", layout="wide")

st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&family=Playfair+Display:ital,wght@0,900;1,900&display=swap');
    
    html, body, [class*="stApp"] {
        font-family: 'Inter', sans-serif;
        background-color: #0b0f19;
        color: #ffffff;
    }

    .content-section { padding: 40px 0; border-bottom: 1px solid #1e293b; width: 100%; }
    .section-num { font-size: 0.8rem; font-weight: 900; color: #4ade80; margin-bottom: 5px; }
    .section-title { font-size: 2.2rem; font-weight: 900; margin-bottom: 15px; letter-spacing: -0.02em; }
    
    /* Benefit & Metric Cards */
    .benefit-card { background: #161b28; padding: 30px; border: 1px solid #2d3748; border-radius: 4px; height: 100%; transition: all 0.3s ease; }
    .benefit-header { font-size: 1.6rem; font-weight: 900; color: #ffffff; margin-bottom: 15px; }
    .benefit-body { font-size: 1.05rem; color: #f8fafc; line-height: 1.6; }

    .metric-card { background: #111827; padding: 20px; border: 1px solid #1e293b; border-radius: 8px; text-align: center; }
    .metric-value { font-size: 1.8rem; font-weight: 900; color: #4ade80; }
    .metric-label { font-size: 0.7rem; color: #94a3b8; text-transform: uppercase; font-weight: 700; margin-top: 5px; }

    /* Anchor Tag UI */
    .anchor-pill { display: inline-block; padding: 4px 10px; border-radius: 4px; font-size: 0.75rem; font-weight: 700; background: #1e293b; color: #f8fafc; border: 1px solid #334155; margin: 4px; }
    .anchor-hit { border-color: #4ade80; color: #4ade80; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. DATA ENGINE: MASTER FILE & GITHUB JSON ---
@st.cache_data(ttl=3600)
def load_map_assets():
    # Source: arcee123/GIS_GEOJSON_CENSUS_TRACTS (FIPS 22 for Louisiana)
    url = "https://raw.githubusercontent.com/arcee123/GIS_GEOJSON_CENSUS_TRACTS/master/22.json"
    geojson = requests.get(url).json()
    
    # Load Opportunity Zones Master File (Mocking structure for script completeness)
    # The 'GEOID' column must match the 'GEOID' in the GeoJSON properties
    master_df = pd.DataFrame({
        "GEOID": [f["properties"]["GEOID"] for f in geojson["features"]],
        "Eligibility": np.random.choice([0, 1], size=len(geojson["features"])), # 1 = Highlighted Green
        "Poverty Rate": np.random.uniform(15, 45, size=len(geojson["features"])),
        "Median Income": np.random.randint(18000, 65000, size=len(geojson["features"])),
        "Parish": "Orleans",
        "Region": "Southeast"
    })
    return geojson, master_df

geojson_data, oz_master = load_map_assets()

# --- SECTIONS 1-2 (Progress Bar & Benefits) ---
st.markdown("<div style='width: 100%; background-color: #1e293b; height: 6px; margin-bottom: 40px;'><div style='width: 75%; height: 100%; background-color: #4ade80;'></div></div>", unsafe_allow_html=True)

# --- SECTION 4: STRATEGIC SELECTION TOOL ---
st.markdown("<div class='content-section'><div class='section-num'>SECTION 4</div><div class='section-title'>Strategic Selection Tool</div></div>", unsafe_allow_html=True)

map_col, profile_col = st.columns([4, 6])

with map_col:
    # Filter for Green Highlighted Tracks (OZ 2.0 Eligible)
    # We use a discrete color map to ensure only eligible tracks are green.
    fig = px.choropleth(
        oz_master,
        geojson=geojson_data,
        locations="GEOID",
        featureidkey="properties.GEOID",
        color="Eligibility",
        color_discrete_map={1: "#4ade80", 0: "#1e293b"},
        projection="mercator"
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r":0,"t":0,"l":0,"b":0},
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        showlegend=False,
        height=650
    )
    
    # Capture map selection
    selected_event = st.plotly_chart(fig, use_container_width=True, on_select="rerun")

with profile_col:
    # Default tract selection or interactive selection
    target_geoid = "22071001700" 
    if selected_event and selected_event["selection"]["points"]:
        target_geoid = selected_event["selection"]["points"][0]["location"]
    
    tract_data = oz_master[oz_master["GEOID"] == target_geoid].iloc[0]

    st.markdown(f"""
        <div style='padding-left:10px;'>
            <h2 style='margin-bottom:0;'>Tract {target_geoid}</h2>
            <p style='color:#4ade80; font-weight:800; text-transform:uppercase;'>{tract_data['Parish']} Parish | {tract_data['Region']} Region</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Metric Cards (Populated from Master File)
    m1, m2, m3 = st.columns(3)
    with m1: st.markdown(f"<div class='metric-card'><div class='metric-value'>{tract_data['Poverty Rate']:.1f}%</div><div class='metric-label'>Poverty Rate</div></div>", unsafe_allow_html=True)
    with m2: st.markdown(f"<div class='metric-card'><div class='metric-value'>${tract_data['Median Income']/1000:.1f}K</div><div class='metric-label'>Median Income</div></div>", unsafe_allow_html=True)
    with m3: st.markdown("<div class='metric-card'><div class='metric-value'>Eligible</div><div class='metric-label'>OZ 2.0 Status</div></div>", unsafe_allow_html=True)

    # 7 Anchors (Example of filtering anchors based on target_geoid)
    st.markdown("<div style='margin-top:30px; padding:25px; background:#161b28; border-radius:8px; border:1px solid #1e293b;'>", unsafe_allow_html=True)
    st.markdown("<p style='font-size:0.8rem; font-weight:900; color:#94a3b8; text-transform:uppercase; margin-bottom:15px;'>Infrastructure & Community Anchors</p>", unsafe_allow_html=True)
    
    anchors = ["Port of New Orleans", "LSU Health", "MSY Airport", "Main St. Hub", "Fiber Node", "Transit Center", "Medical Center"]
    for a in anchors:
        st.markdown(f"<div class='anchor-pill anchor-hit'>✔ {a}</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)