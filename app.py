# This specific block in the script handles the Column Q "Cleaning"
def determine_highlight_status(row):
    # This targets Column Q ('insider_nominated')
    insider_val = str(row.get('insider_nominated', '')).lower().strip()
    
    # Cleaning Logic:
    if insider_val in ['yes', '1', 'true', 'eligible', '1.0']:
        return "Eligible"
    
    # Fallback to ACS and Math to reach the full 620 count
    # ... rest of the function ...