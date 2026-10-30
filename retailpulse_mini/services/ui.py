"""Shared dashboard/report filters and compact chart presentation."""
import os

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

from database.queries import filter_options, sales_data
from services.analytics import analyze


def currency():
    return os.getenv('CURRENCY_SYMBOL', 'INR')


def filtered_analysis():
    bounds, categories, places = filter_options()
    if bounds['first_date'] is None:
        st.info('Your database is ready. Upload your first sales file to begin.')
        st.page_link('pages/upload.py', label='Go to Upload Data', icon='📤')
        st.stop()
    # A non-widget state entry preserves the same filters when switching pages.
    saved = st.session_state.get('sales_filters', {})
    with st.expander('Filter sales', expanded=True):
        a, b = st.columns(2)
        dates = a.date_input('Date range', value=saved.get('dates', (bounds['first_date'], bounds['last_date'])),
                             min_value=bounds['first_date'], max_value=bounds['last_date'])
        selected_categories = b.multiselect('Product category', categories,
                                             default=[v for v in saved.get('categories', []) if v in categories])
        c, d = st.columns(2)
        regions = sorted(places.region.unique())
        cities = sorted(places.city.unique())
        selected_regions = c.multiselect('Region', regions, default=[v for v in saved.get('regions', []) if v in regions])
        selected_cities = d.multiselect('City', cities, default=[v for v in saved.get('cities', []) if v in cities])
    if len(dates) != 2:
        st.info('Choose both a start and end date.')
        st.stop()
    filters = dict(dates=dates, categories=selected_categories, regions=selected_regions, cities=selected_cities)
    st.session_state['sales_filters'] = filters
    data = sales_data(*dates, categories=selected_categories, cities=selected_cities, regions=selected_regions)
    if data.empty:
        st.info('No sales match these filters. Widen the date range or clear a selection.')
        st.stop()
    st.caption(f'{dates[0]} to {dates[1]} · {len(data):,} order lines · Currency: {currency()} · Source: MySQL')
    return analyze(data), filters


def show_kpis(kpis):
    columns = st.columns(3)
    for i, (name, value) in enumerate(kpis.items()):
        if name == 'Profit margin':
            display = f'{value:.2f}%' if value is not None else 'N/A'
        elif name in ['Total orders', 'Total customers']:
            display = f'{value:,}'
        else:
            display = f'{currency()} {value:,.2f}'
        columns[i % 3].metric(name, display)
    st.caption('Orders and customers are distinct within the filtered lines. Average order value uses '
               'filtered revenue per distinct order; margin is total profit / total revenue. Zero-revenue margin is N/A.')


def chart(frame, kind, x, y, title, horizontal=False):
    sns.set_theme(style='whitegrid', palette=['#0f766e', '#f59e0b'])
    fig, ax = plt.subplots(figsize=(8, 3.8))
    try:
        if kind == 'line':
            ax.plot(frame[x], frame[y], color='#0f766e', marker='o', linewidth=2)
            fig.autofmt_xdate()
        elif kind == 'compare':
            frame.set_index(x)[['revenue', 'profit']].plot.bar(ax=ax, color=['#0f766e', '#f59e0b'])
            ax.legend(frameon=False)
        elif horizontal:
            sns.barplot(data=frame, x=y, y=x, color='#0f766e', ax=ax)
        else:
            sns.barplot(data=frame, x=x, y=y, color='#0f766e', ax=ax)
        ax.set_title(title, loc='left', weight='bold', pad=15)
        ax.set_xlabel(currency() if horizontal else '')
        ax.set_ylabel('' if horizontal else currency())
        if not horizontal and kind != 'line':
            ax.tick_params(axis='x', rotation=25)
        sns.despine(ax=ax)
        fig.tight_layout()
        st.pyplot(fig)
    finally:
        plt.close(fig)
