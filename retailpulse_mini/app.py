from pathlib import Path

import streamlit as st

st.set_page_config(page_title='Elevate', page_icon='📊', layout='wide')
st.markdown(f"<style>{(Path(__file__).parent / 'assets/style.css').read_text(encoding='utf-8')}</style>",
            unsafe_allow_html=True)


def home():
    st.markdown('<div class="eyebrow">EXPLORE THE DATA YOU HAVE</div>', unsafe_allow_html=True)
    st.title('Elevate')
    st.subheader('Flexible analytics for any tabular domain')
    st.write('Upload a CSV or Excel table with your own columns. Review types, save it to MySQL, '
             'choose measures and categories, and ask questions about that dataset.')
    st.divider()
    for column, title, body in zip(st.columns(3),
                                   ['01 · Bring your data', '02 · Find the story', '03 · Share the insight'],
                                   ['Upload CSV or Excel. Review quality issues before saving clean rows.',
                                    'Explore numeric summaries, category comparisons, and date trends.',
                                    'Ask Elevate a question, or download a report for your team.']):
        with column:
            with st.container(border=True):
                st.subheader(title)
                st.write(body)
    st.page_link('pages/upload.py', label='Start with Upload Data', icon='📤')
    sample = Path(__file__).parent / 'sample_data/retail_sales.csv'
    st.download_button('Download sample data · 5,000 records', sample.read_bytes(),
                       file_name='retail_sales.csv', mime='text/csv')
    st.caption('Fictional sample · 2024–2025 · 2,500 orders · 20 products · 4 regions · INR')
    with st.expander('Before you start'):
        st.write('For an existing installation, run database/generic_schema.sql once as root in Workbench. '
                 'For a new installation, first complete database/schema.sql and account setup. See GENERIC_DATA_GUIDE.md.')
        st.write('Flexible datasets have no required retail columns. Missing business measures cannot be computed without '
                 'their inputs. Flat CSV and .xlsx tables are supported; PDFs, images and nested JSON are not.')
        st.download_button('Download one-time MySQL upgrade script',
                           (Path(__file__).parent / 'database/generic_schema.sql').read_bytes(),
                           'generic_schema.sql', 'text/plain')
        st.download_button('Download dataset deletion permissions script',
                           (Path(__file__).parent / 'database/enable_dataset_deletion.sql').read_bytes(),
                           'enable_dataset_deletion.sql', 'text/plain')


with st.sidebar:
    st.markdown('## ◈ Elevate')
    st.caption('FLEXIBLE DATA ANALYTICS')
    st.selectbox('Workflow', ['Flexible datasets', 'Original retail'], key='workflow')
page = st.navigation([
    st.Page(home, title='Home', icon='🏠', default=True),
    st.Page('pages/upload.py', title='Upload Data', icon='📤'),
    st.Page('pages/dashboard.py', title='Data Dashboard', icon='📊'),
    st.Page('pages/chatbot.py', title='Ask Data Chatbot', icon='💬'),
    st.Page('pages/reports.py', title='Download Report', icon='📥'),
])
with st.sidebar:
    st.divider()
    st.caption('Python + MySQL\n\nYour next decision starts with better data.')
page.run()
