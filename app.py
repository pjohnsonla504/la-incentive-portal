# --- REVISED NMTC LOGIC TO MATCH POLICYMAP / CDFI 2025 ---
@st.cache_data(ttl=60)
def load_data():
    master = pd.read_csv("tract_data_final.csv")
    master.columns = [str(c).strip() for c in master.columns]
    
    # Standardize data types
    cols = ['poverty_rate', 'unemp_rate', 'med_hh_income', 'pop_total']
    for col in cols:
        master[col] = pd.to_numeric(master[col].astype(str).replace(r'[\$,%]', '', regex=True), errors='coerce').fillna(0)
    
    state_median = master['med_hh_income'].median()
    nat_unemp_bench = 6.0 

    # 1. NMTC BASE ELIGIBILITY
    master['nmtc_eligible'] = np.where(
        (master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (state_median * 0.8)), 1, 0
    )
    
    # 2. SEVERE DISTRESS (Standard NMTC)
    is_severe = (
        (master['poverty_rate'] >= 30) | 
        (master['med_hh_income'] <= (state_median * 0.6)) | 
        (master['unemp_rate'] >= (nat_unemp_bench * 1.5))
    )

    # 3. DEEP DISTRESS (OZ 2.0 & PolicyMap Conformity)
    # This now includes the 'Rural Severe' bump that matches Tract 22075050100
    urban_parishes = ['Orleans', 'Jefferson', 'East Baton Rouge', 'Caddo', 'Lafayette', 'St. Tammany']
    master['is_rural'] = np.where((~master['Parish'].isin(urban_parishes)) & (master['pop_total'] < 5000), 1, 0)

    cond_poverty_40 = (master['poverty_rate'] >= 40)
    cond_income_40  = (master['med_hh_income'] <= (state_median * 0.4))
    cond_unemp_25   = (master['unemp_rate'] >= (nat_unemp_bench * 2.5))
    cond_rural_severe = (master['is_rural'] == 1) & is_severe # The PolicyMap 'Deep' trigger

    master['deep_distress'] = np.where(
        cond_poverty_40 | cond_income_40 | cond_unemp_25 | cond_rural_severe, 1, 0
    )

    with open("tl_2025_22_tract.json") as f:
        geojson = json.load(f)
    return master, geojson