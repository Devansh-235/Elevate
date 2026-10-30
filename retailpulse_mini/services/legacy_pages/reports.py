import streamlit as st

from database.connection import DatabaseError
from services.analytics import business_findings
from services.report_generator import csv_bytes, findings_text, kpi_excel
from services.ui import currency, filtered_analysis, show_kpis

st.title('Download Report')
st.write('Export a consistent snapshot of your filtered sales performance.')
try:
    result, filters = filtered_analysis()
    show_kpis(result['kpis'])
    findings = business_findings(result, currency())
    a, b, c = st.columns(3)
    with a:
        st.subheader('Sales data')
        st.write('Every order line matching your filters.')
        st.download_button('Download CSV', csv_bytes(result['data']), 'elevate_filtered_sales.csv', 'text/csv')
    with b:
        st.subheader('KPI summary')
        st.write('Six key metrics with filter context.')
        st.download_button('Download Excel', kpi_excel(result, filters, currency()), 'elevate_kpis.xlsx',
                           'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    with c:
        st.subheader('Business findings')
        st.write('A plain-language report ready to share.')
        st.download_button('Download text report', findings_text(findings, filters, currency()),
                           'elevate_findings.txt', 'text/plain')
    st.subheader('Report preview')
    for finding in findings:
        st.write('• ' + finding)
except DatabaseError as exc:
    st.error(str(exc))
