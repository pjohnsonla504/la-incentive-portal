# --- UPDATED NMTC LOGIC SECTION ---
def load_data():
    # ... (existing loading code) ...
    
    state_median = master['med_hh_income'].median()
    
    # Tier 1: Base Eligibility
    master['nmtc_eligible'] = np.where(
        (master['poverty_rate'] >= 20) | (master['med_hh_income'] <= (state_median * 0.8)), 1, 0
    )
    
    # Tier 2: Severe Distress (The 30% mark)
    master['severe_distress'] = np.where(
        (master['poverty_rate'] >= 30) | (master['med_hh_income'] <= (state_median * 0.6)) | (master['unemp_rate'] >= 9.0), 1, 0
    )
    
    # Tier 3: Deep Distress (The 40% mark you requested)
    master['deep_distress'] = np.where(
        (master['poverty_rate'] >= 40) | (master['med_hh_income'] <= (state_median * 0.4)) | (master['unemp_rate'] >= 15.0), 1, 0
    )
    
    return master, geojson

# --- UPDATED DISPLAY BOXES ---
with col_metrics:
    # ... (existing profile metrics) ...
    
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(glow_box("URBAN", is_urban, "#dc3545"), unsafe_allow_html=True)
        st.markdown(glow_box("RURAL", is_rural, "#28a745"), unsafe_allow_html=True)
    with c2:
        # Top box shows general eligibility
        st.markdown(glow_box("NMTC ELIGIBLE", is_nmtc, "#28a745"), unsafe_allow_html=True)
        # Bottom box now only glows if it hits that 40% "Deep Distress" threshold
        st.markdown(glow_box("DEEP DISTRESS (40%+)", is_deep, "#28a745"), unsafe_allow_html=True)