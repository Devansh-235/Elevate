import hashlib

import streamlit as st

from database.connection import DatabaseError
from database.queries import insert_cleaned, upload_history
from services.data_cleaning import DATE_FORMATS, clean_data, read_upload
from services.report_generator import csv_bytes

st.title('Upload Data')
st.write('Preview, validate, then save clean sales records to MySQL.')
st.caption('CSV or .xlsx · Up to 20 MB / 100,000 rows · Excel: first worksheet only · Discount 0–1')
file = st.file_uploader('Choose a retail sales file', type=['csv', 'xlsx'])
date_choice = st.selectbox('Date format in your file', list(DATE_FORMATS))
if file:
    try:
        content = file.getvalue()
        raw = read_upload(content, file.name)
        st.subheader('Original preview')
        st.dataframe(raw.head(100), width='stretch')
        valid, rejected, summary = clean_data(raw, DATE_FORMATS[date_choice])
        for col, key, label in zip(st.columns(5), ['total', 'valid', 'invalid', 'duplicates', 'missing_cells'],
                                   ['Total rows', 'Valid rows', 'Invalid rows', 'Duplicate rows', 'Missing cells']):
            col.metric(label, f'{summary[key]:,}')
        st.caption('Validation counts apply to this file. Database conflicts are checked during the atomic import.')
        with st.expander('Cleaned preview', expanded=True):
            st.dataframe(valid.head(100), width='stretch')
        if not rejected.empty:
            st.warning('Rejected rows will not be inserted. Download the reasons to correct your source file.')
            st.dataframe(rejected.head(100), width='stretch')
            st.download_button('Download rejected records', csv_bytes(rejected), 'rejected_records.csv', 'text/csv')
        if st.button('Insert cleaned records into MySQL', type='primary', disabled=valid.empty):
            with st.spinner('Saving this import in one transaction…'):
                count = insert_cleaned(valid, file.name, hashlib.sha256(content).hexdigest(),
                                       summary['total'], summary['invalid'])
            st.success(f'{count:,} records inserted. Your dashboard is ready.')
            st.page_link('pages/dashboard.py', label='Open Sales Dashboard', icon='📊')
    except (ValueError, DatabaseError) as exc:
        st.error(str(exc))

with st.expander('Recent successful imports'):
    try:
        st.dataframe(upload_history(), width='stretch', hide_index=True)
    except DatabaseError as exc:
        st.info(str(exc))
