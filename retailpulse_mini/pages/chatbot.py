from pathlib import Path
import runpy
import streamlit as st

if st.session_state.get('workflow') == 'Original retail':
    runpy.run_path(str(Path(__file__).resolve().parents[1] / 'services/legacy_pages/chatbot.py'))
else:
    from services.dataset_ui import chatbot_page
    chatbot_page()
