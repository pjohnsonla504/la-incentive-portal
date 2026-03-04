import dash
from dash import dcc, html, Input, Output, State
import dash_leaflet as dl
import pandas as pd
import json

# --- Data Loading ---
# Loading the Master File per your instruction
df = pd.read_csv('Opportunity Zones 2.0 - Master Data File (V2).csv')

# Pre-processing GEOID to string to ensure matching with GeoJSON
df['GEOID'] = df['GEOID'].astype(str)

# --- App Layout ---
app = dash.Dash(__name__)

app.layout = html.Div([
    html.H1("Opportunity Zones 2.0 & 1.0 Analysis", style={'textAlign': 'center'}),
    
    html.Div([
        # Metric Cards Container
        html.Div([
            html.Div([html.H4("Metro Status"), html.P(id="metro-status-card", children="Select a tract")], 
                     className="card", style={'padding': '10px', 'border': '1px solid #ccc', 'margin': '5px'}),
            html.Div([html.H4("OZ 2.0 Eligibility"), html.P(id="oz2-eligibility-card", children="Select a tract")], 
                     className="card", style={'padding': '10px', 'border': '1px solid #ccc', 'margin': '5px'}),
        ], style={'display': 'flex', 'flexDirection': 'row', 'justifyContent': 'center'}),
        
        # Map Container
        dl.Map(center=[31.0, -92.0], zoom=7, children=[
            dl.TileLayer(),
            dl.LayersControl([
                # Base Layer: OZ 2.0 Eligibility (Highlighted Green per instructions)
                dl.Overlay(
                    dl.GeoJSON(
                        id="oz2-layer",
                        # Placeholder for GeoJSON data
                        data=None, 
                        options=dict(style=dict(color="green", weight=2, fillOpacity=0.5)),
                        hoverStyle=dict(weight=5, color='#666', dashArray=''),
                    ), name="Opportunity Zone 2.0 Eligibility", checked=True
                ),
                # New Layer: OZ 1.0 Eligibility (Column D)
                dl.Overlay(
                    dl.GeoJSON(
                        id="oz1-layer",
                        data=None,
                        options=dict(style=dict(color="blue", weight=2, fillOpacity=0.3)),
                    ), name="Current OZ 1.0 (Expires 2028)", checked=False
                ),
            ]),
        ], style={'width': '100%', 'height': '70vh'}, id="map"),
    ])
])

# --- Callbacks ---

@app.callback(
    [Output("metro-status-card", "children"),
     Output("oz2-eligibility-card", "children")],
    [Input("oz2-layer", "click_feature")]
)
def update_metrics(feature):
    if feature is None:
        return "Select a tract", "Select a tract"
    
    geoid = feature['properties']['GEOID']
    row = df[df['GEOID'] == geoid]
    
    if not row.empty:
        # Sourcing Metro Status from Column G (Rural Eligibility)
        metro_status = row.iloc[0]['Rural Eligibility for OZ 2.0']
        # Sourcing OZ 2.0 Status
        oz2_status = row.iloc[0]['Eligibility for OZ 2.0 Designation']
        
        return metro_status, oz2_status
    
    return "Data not found", "Data not found"

if __name__ == '__main__':
    app.run_server(debug=True)