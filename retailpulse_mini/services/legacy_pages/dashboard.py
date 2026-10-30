import streamlit as st

from database.connection import DatabaseError
from services.analytics import business_findings
from services.ui import chart, currency, filtered_analysis, show_kpis

st.title('Sales Dashboard')
st.write('A clear view of revenue, profitability, and the products driving performance.')
try:
    result, filters = filtered_analysis()
    show_kpis(result['kpis'])
    left, right = st.columns(2)
    with left:
        chart(result['monthly'], 'line', 'month', 'revenue', 'Monthly sales trend')
        top = result['products'].sort_values(['revenue', 'product_id'], ascending=[False, True]).head(5).copy()
        top['label'] = top.product_name + ' · ' + top.product_id
        chart(top, 'bar', 'label', 'revenue', 'Top five products by revenue', horizontal=True)
    with right:
        chart(result['category'], 'bar', 'category', 'revenue', 'Category-wise revenue', horizontal=True)
        chart(result['regions'], 'bar', 'region', 'revenue', 'Region-wise sales')
    comparison = result['monthly'].copy()
    comparison['month'] = comparison['month'].dt.strftime('%b %Y')
    chart(comparison, 'compare', 'month', 'revenue', 'Monthly revenue versus profit')
    st.subheader('Business findings')
    for finding in business_findings(result, currency()):
        st.write('• ' + finding)
    with st.expander('Explore filtered sales data'):
        st.dataframe(result['data'], width='stretch', hide_index=True)
except DatabaseError as exc:
    st.error(str(exc))
