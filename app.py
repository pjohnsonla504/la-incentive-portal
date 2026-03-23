def render_map_go(df):
        map_df = df.copy().reset_index(drop=True)
        selected_geoids = [rec['Tract'] for rec in st.session_state["session_recs"]]
        def get_color_cat(row):
            if row['geoid_str'] in selected_geoids: return 2
            return 1 if row['Eligibility_Status'] == 'Eligible' else 0
        map_df['Color_Category'] = map_df.apply(get_color_cat, axis=1)
        
        if st.session_state.get("active_tract") and st.session_state["active_tract"] in map_df['geoid_str'].values:
            focus_geoids = {st.session_state["active_tract"]}
        else:
            focus_geoids = set(map_df['geoid_str'].tolist())
            
        center, zoom = get_zoom_center(focus_geoids)
        sel_idx = map_df.index[map_df['geoid_str'] == st.session_state["active_tract"]].tolist() if st.session_state["active_tract"] else []
        
        revision_key = "_".join(sorted(list(focus_geoids))) if len(focus_geoids) < 5 else str(hash(tuple(sorted(list(focus_geoids)))))

        fig = go.Figure()

        fig.add_trace(go.Choroplethmapbox(
            geojson=gj, 
            locations=map_df['geoid_str'], 
            z=map_df['Color_Category'],
            featureidkey="properties.GEOID" if "GEOID" in str(gj) else "properties.GEOID20",
            colorscale=[[0, '#e2e8f0'], [0.5, '#4ade80'], [1, '#f97316']], 
            zmin=0, zmax=2,
            showscale=False, 
            # Boundary lines are now black and more defined
            marker=dict(opacity=0.6, line=dict(width=1.2, color='black')),
            selectedpoints=sel_idx, 
            hoverinfo="location",
            name="Census Tracts"
        ))

        # --- ANCHOR PINS ---
        anchor_types = sorted(anchors_df['Type'].unique())
        color_palette = px.colors.qualitative.Bold 

        for i, a_type in enumerate(anchor_types):
            type_data = anchors_df[anchors_df['Type'] == a_type]
            marker_color = "#f97316" if a_type == "Project Announcements" else color_palette[i % len(color_palette)]
            marker_symbol = "star" if a_type == "Project Announcements" else "circle"
            marker_size = 15 if a_type == "Project Announcements" else 11

            fig.add_trace(go.Scattermapbox(
                lat=type_data['Lat'],
                lon=type_data['Lon'],
                mode='markers',
                marker=go.scattermapbox.Marker(size=marker_size, color=marker_color, symbol=marker_symbol),
                text=type_data['Name'],
                hoverinfo='text',
                name=f"{a_type}",
                visible="legendonly" 
            ))

        fig.update_layout(
            mapbox=dict(style="carto-positron", zoom=zoom, center=center),
            margin={"r":0,"t":0,"l":0,"b":0}, 
            paper_bgcolor='rgba(0,0,0,0)',
            height=700, 
            clickmode='event+select', 
            uirevision=revision_key,
            legend=dict(
                title=dict(text="<b>Toggle Anchor Assets</b>", font=dict(size=12)),
                yanchor="top", y=0.98, xanchor="left", x=0.02,
                bgcolor="rgba(255, 255, 255, 0.9)",
                font=dict(size=11, color="#1e293b"),
                bordercolor="#cbd5e1", borderwidth=1
            )
        )
        return fig