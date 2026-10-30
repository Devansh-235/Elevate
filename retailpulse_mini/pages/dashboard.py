from pathlib import Path
import runpy
import streamlit as st

if st.session_state.get('workflow') == 'Original retail':
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'services/legacy_pages/dashboard.py'))
else:
    from services.dataset_ui import dashboard_page
    dashboard_page()
