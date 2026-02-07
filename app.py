import os

@st.cache_data(ttl=60)
def load_data():
    # This line finds the directory where THIS script is saved
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    # Construct paths relative to the script location
    csv_path = os.path.join(BASE_DIR, "Opportunity Zones 2.0 - Master Data File.csv")
    json_path = os.path.join(BASE_DIR, "la_tracts_2024.json")

    # Debugging: If it still fails, this will show you exactly what path it's looking for
    if not os.path.exists(json_path):
        st.error(f"FATAL: Missing GeoJSON at {json_path}")
        st.stop()
    if not os.path.exists(csv_path):
        st.error(f"FATAL: Missing CSV at {csv_path}")
        st.stop()

    # Proceed with loading
    with open(json_path) as f: 
        la_geojson = json.load(f)
        
    # ... rest of your loading logic ...
    # (Ensure you use the same logic for the CSV loading below)