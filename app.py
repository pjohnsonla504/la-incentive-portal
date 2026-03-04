import dash
from dash import dcc, html, Input, Output
import dash_leaflet as dl
import pandas as pd
import os

# --- Data Loading ---
# Loading the Master File per your instruction
FILE_NAME = 'Opportunity Zones 2.0 - Master Data File (V2).csv'

if os.path.exists(FILE_NAME):
    df = pd.read_csv(FILE_NAME)
    # Ensure GEOID is a string for mapping and handle column G naming
    df['GEOID'] = df['GEOID'].astype(str)
else:
    df = pd.DataFrame() # Fallback if file is missing

# --- App Layout ---
app = dash.Dash(__name__)
server = app.server # Needed for deployments

app.layout = html.Div([
    html.H1("Louisiana Opportunity Zones Portal", style={'textAlign': 'center', 'fontFamily': 'sans-serif'}),
    
    # Metric Cards
    html.Div([
        html.Div([
            html.B("Metro Status (Col G)"),
            html.P(id="metro-status-card", children="Select a tract")
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px', 'margin': '10px', 'width': '200px', 'backgroundColor': '#f9f9f9'}),
        
        html.Div([
            html.B("OZ 2.0 Eligibility"),
            html.P(id="oz2-eligibility-card", children="Select a tract")
        ], style={'padding': '20px', 'border': '1px solid #ddd', 'borderRadius': '10px', 'margin': '10px', 'width': '200px', 'backgroundColor': '#f9f9f9'}),
    ], style={'display': 'flex', 'justifyContent': 'center', 'textAlign': 'center'}),

    # Map Control
    dl.Map(center=[31.0, -92.0], zoom=7, children=[
        dl.TileLayer(),
        dl.LayersControl([
            # Base Layer: OZ 2.0 (Green Highlight)
            dl.Overlay(
                dl.GeoJSON(
                    id="oz2-layer",
                    data=None, # This would be populated by your GeoJSON source
                    options=dict(style=dict(color="green", weight=2, fillOpacity=0.5)),
                    hoverStyle=dict(weight=5, color='#666', dashArray=''),
                ), name="Opportunity Zone 2.0 Eligibility", checked=True
            ),
            # New Layer: OZ 1.0 (Column D)
            dl.Overlay(
                dl.GeoJSON(
                    id="oz1-layer",
                    data=None, 
                    options=dict(style=dict(color="blue", weight=2, fillOpacity=0.3)),
                ), name="Current OZ 1.0 (Expires 2028)", checked=False
            ),
        ]),
    ], style={'width': '100%', 'height': '70vh', 'margin': 'auto'}, id="map"),
    
    # Store data for client-side if needed
    dcc.Store(id='selected-tract-data')
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
    
    # Get GEOID from the clicked map feature
    geoid = str(feature['properties']['GEOID'])
    
    # Filter the dataframe
    target_row = df[df['GEOID'] == geoid]
    
    if not target_row.empty:
        # Column G: Rural Eligibility for OZ 2.0
        metro_status = target_row.iloc[0]['Rural Eligibility for OZ 2.0']
        # Column E: Eligibility for OZ 2.0 Designation
        oz2_status = target_row.iloc[0]['Eligibility for OZ 2.0 Designation']
        
        return metro_status, oz2_status
    
    return "Not Found", "Not Found"

if __name__ == '__main__':
    app.run_server(debug=True)