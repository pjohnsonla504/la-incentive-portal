# --- REVISED DATA LOADING WITH FULL DEEP DISTRESS LOGIC ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    
    # Ensure numeric types for comparison
    cols_to_fix = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']
    for col in cols_to_fix:
        if col in master.columns:
            master[col] = pd.to_numeric(master[col].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    # CALCULATE METRICS
    state_median = master['med_hh_income'].median()
    # National Unemployment Benchmark (approx 6.0% for the ACS 5-year average period)
    nat_unemp_bench = 6.0 

    # 1. BASE NMTC ELIGIBILITY
    master['nmtc_eligible'] = np.where(
        (master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (state_median * 0.8)), 
        1, 0
    )
    
    # 2. OFFICIAL DEEP DISTRESS LOGIC (Matching PolicyMap/CDFI Fund)
    # Qualifies if ANY of these 3 are true:
    cond_poverty = (master['poverty_rate'] >= 40)
    cond_income  = (master['med_hh_income'] <= (state_median * 0.4))
    cond_unemp   = (master['unemp_rate'] >= (nat_unemp_bench * 2.5)) # 15% or higher
    
    master['deep_distress'] = np.where(cond_poverty | cond_income | cond_unemp, 1, 0)
    
    # 3. RURAL LOGIC (OZ 2.0 Conformity)
    urban_parishes = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urban_parishes)) & (master['pop_total'] < 5000), 1, 0)

    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson