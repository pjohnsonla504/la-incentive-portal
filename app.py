# --- UPDATE IN SECTION 5 (Industrial & Institutional Asset Map) ---
if gj:
    fig_5 = px.choropleth_mapbox(
        master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
        color="Eligibility_Status", 
        color_discrete_map={"Eligible": "rgba(74, 222, 128, 0.3)", "Ineligible": "rgba(30,41,59,0.1)"},
        mapbox_style="white-bg", # Change this
        zoom=6, center={"lat": 31.0, "lon": -92.0}, opacity=0.5
    )
    
    # Add a reliable tile layer that won't be blocked
    fig_5.update_layout(
        mapbox_layers=[{
            "below": 'traces',
            "sourcetype": "raster",
            "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]
        }]
    )
    
    fig_5.add_trace(go.Scattermapbox(
        lat=anchors_df['Lat'], lon=anchors_df['Lon'], mode='markers',
        marker=go.scattermapbox.Marker(size=8, color='#4ade80'),
        text=anchors_df['Name'], hoverinfo='text'
    ))
    fig_5.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, paper_bgcolor='rgba(0,0,0,0)', height=650, showlegend=False)
    st.plotly_chart(fig_5, use_container_width=True, key="static_map")


# --- UPDATE IN SECTION 6 (Interactive Recommendation Tool) ---
if gj:
    m_col, p_col = st.columns([7, 3])
    with m_col:
        fig_6 = px.choropleth_mapbox(
            master_df, geojson=gj, locations="geoid_str", featureidkey="properties.GEOID",
            color="Eligibility_Status", 
            color_discrete_map={"Eligible": "#4ade80", "Ineligible": "rgba(30,41,59,0.2)"},
            mapbox_style="white-bg", # Change this
            zoom=6.5, center={"lat": 30.8, "lon": -91.8}, opacity=0.7
        )
        
        # Add a reliable tile layer that won't be blocked
        fig_6.update_layout(
            mapbox_layers=[{
                "below": 'traces',
                "sourcetype": "raster",
                "source": ["https://basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png"]
            }],
            coloraxis_showscale=False, margin={"r":0,"t":0,"l":0,"b":0}, 
            paper_bgcolor='rgba(0,0,0,0)', height=600
        )
        selection = st.plotly_chart(fig_6, use_container_width=True, on_select="rerun", key="interactive_map")