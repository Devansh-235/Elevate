"""Flexible dataset pages; only five pages are exposed by app.py."""
import hashlib
import json
import uuid
from io import BytesIO
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from database.connection import DatabaseError
from database.datasets import delete_dataset, get_dataset, list_datasets, load_dataset, save_dataset
from database.queries import save_chat
from services.chatbot_service import ChatbotError, execute_select, explain_results, generate_query
from services.dataset_analytics import summarize
from services.dataset_cleaning import KINDS, clean_table, discover_columns, display_columns, fingerprint, read_table
from services.dataset_reports import export_findings, export_summary
from services.report_generator import csv_bytes


def migration_hint(exc):
    st.error(str(exc))
    st.info('If the datasets tables are missing, run database/generic_schema.sql once in MySQL Workbench as root. '
            'This adds flexible storage and preserves the original retail tables.')


def pick_dataset(allow_delete=False):
    if notice := st.session_state.pop('dataset_deleted_notice', None):
        st.success(notice)
    try:
        available = list_datasets()
    except DatabaseError as exc:
        migration_hint(exc)
        st.stop()
    if available.empty:
        st.info('No flexible datasets have been saved yet. Upload a CSV or Excel file to begin. '
                'Your previous sample sales remain available under Original retail in the sidebar.')
        st.page_link('pages/upload.py', label='Upload a dataset')
        st.stop()
    ids = available.dataset_id.astype(int).tolist()
    labels = {int(row.dataset_id): f'{row.name} · {row.row_count:,} rows · #{row.dataset_id}' for row in available.itertuples()}
    selected = st.session_state.get('selected_dataset', ids[0])
    if selected not in ids:
        selected = ids[0]
    value = st.selectbox('Dataset', ids, index=ids.index(selected), format_func=labels.get)
    st.session_state.selected_dataset = value
    dataset = get_dataset(value)
    if allow_delete:
        delete_controls(dataset)
    return dataset


def delete_controls(dataset):
    dataset_id = int(dataset['dataset_id'])
    with st.expander('Manage dataset · Delete'):
        st.write(f"Delete **{dataset['name']}** (#{dataset_id}), containing {dataset['row_count']:,} rows.")
        st.caption('This permanently removes this dataset and its stored rows. Other datasets and original retail data '
                   'remain. Downloaded reports and historical chat audit logs are retained.')
        with st.form(f'delete_dataset_{dataset_id}'):
            confirmed = st.checkbox('I confirm that I want to permanently delete this dataset.')
            submitted = st.form_submit_button('Delete selected dataset')
        if submitted:
            if not confirmed:
                st.warning('Tick the confirmation checkbox before deleting.')
                return
            try:
                removed = delete_dataset(dataset_id)
            except DatabaseError as exc:
                st.error(str(exc))
                st.info('If MySQL reports permission error 1142, run database/enable_dataset_deletion.sql once as root in Workbench.')
                return
            for key in [f'selection_{dataset_id}', f'dataset_chat_{dataset_id}', f'dataset_chat_{dataset_id}_session', 'selected_dataset']:
                st.session_state.pop(key, None)
            st.session_state.dataset_deleted_notice = f"Deleted {dataset['name']} and {removed:,} stored rows."
            st.rerun()


def upload_page():
    st.title('Upload Data')
    st.write('Import a flat table from any domain. No fixed retail columns are required.')
    st.caption('CSV or .xlsx · 20 MB · 100,000 rows · 150 columns · text cells up to 2,048 characters')
    file = st.file_uploader('Choose your dataset', type=['csv', 'xlsx'])
    if file is None:
        return
    content = file.getvalue()
    if len(content) > 20 * 1024 * 1024:
        st.error('Choose a file smaller than 20 MB.')
        return
    try:
        sheet = 0
        separator = ','
        if file.name.lower().endswith('.xlsx'):
            with pd.ExcelFile(BytesIO(content), engine='openpyxl') as workbook:
                sheet = st.selectbox('Worksheet', workbook.sheet_names)
        else:
            separator = st.selectbox('CSV separator', [',', ';', '\t', '|'], format_func=lambda x: 'Tab' if x == '\t' else x)
        header = int(st.number_input('Header row (1 = first row)', min_value=1, max_value=100, value=1))
        raw = read_table(content, file.name, sheet, header, separator)
        st.subheader('Original preview')
        st.dataframe(raw.head(100), width='stretch')
        token = hashlib.sha256(content + str(sheet).encode() + str(header).encode() + separator.encode()).hexdigest()[:16]
        name = st.text_input('Dataset name', value=Path(file.name).stem, max_chars=180)
        st.subheader('Review column types')
        st.caption('Text keeps IDs and labels intact. Number accepts negative values and does not assume currency. '
                   'Choose Date only for date/timestamp fields. Mixed-format columns default to Text to avoid data loss.')
        schema = st.data_editor(pd.DataFrame(discover_columns(raw)), hide_index=True, width='stretch',
                                disabled=['name', 'sql_name'], key='schema_' + token,
                                column_config={'name': 'Original column', 'sql_name': 'SQL column',
                                               'kind': st.column_config.SelectboxColumn('Type', options=KINDS, required=True)})
        columns = schema.to_dict('records')
        left, right = st.columns(2)
        date_format = left.selectbox('Date parsing', ['ISO8601', '%d/%m/%Y', '%m/%d/%Y'],
                                     format_func=lambda v: {'ISO8601': 'ISO dates / Excel date cells', '%d/%m/%Y': 'DD/MM/YYYY', '%m/%d/%Y': 'MM/DD/YYYY'}[v])
        invalid_policy = right.selectbox('If a chosen type cannot parse a value', ['Reject rows', 'Set invalid cells to missing'])
        drop_duplicates = st.checkbox('Remove exact duplicate rows', value=False)
        st.caption('Duplicates are kept by default: repeated observations may be legitimate. Missing cells are kept as NULL; no values are invented.')
        valid, rejected, quality, warnings = clean_table(raw, columns, drop_duplicates, invalid_policy, date_format, header)
        for col, (label, value) in zip(st.columns(5), quality.items()):
            col.metric(label, f'{value:,}')
        for warning in warnings:
            st.warning(warning)
        with st.expander('Accepted data preview', expanded=True):
            st.dataframe(display_columns(valid, columns).head(100), width='stretch')
        if not rejected.empty:
            st.warning('Some rows were rejected. Review the reason column before saving.')
            st.dataframe(rejected.head(100), width='stretch')
            st.download_button('Download rejected records', csv_bytes(rejected), 'rejected_records.csv', 'text/csv')
        if st.button('Save dataset to MySQL', type='primary', disabled=valid.empty or not name.strip()):
            digest = fingerprint(content, sheet, header, columns, [separator, drop_duplicates, invalid_policy, date_format])
            with st.spinner('Saving dataset atomically…'):
                dataset_id, created = save_dataset(valid, columns, name, file.name, digest, len(rejected))
            st.session_state.selected_dataset = dataset_id
            st.success(f'{len(valid):,} rows saved as dataset #{dataset_id}.' if created else
                       f'This file and cleaning configuration were already saved as dataset #{dataset_id}. No duplicates added.')
            st.page_link('pages/dashboard.py', label='Open Data Dashboard')
    except DatabaseError as exc:
        migration_hint(exc)
    except Exception as exc:
        st.error(f'Could not prepare this file: {exc}')


def analysis_selection(dataset):
    data = load_dataset(dataset)
    columns = dataset['columns']
    labels = {c['sql_name']: c['name'] for c in columns}
    numeric = [c['sql_name'] for c in columns if c['kind'] == 'Number']
    text = [c['sql_name'] for c in columns if c['kind'] == 'Text']
    dates = [c['sql_name'] for c in columns if c['kind'] == 'Date']
    key = 'selection_' + str(dataset['dataset_id'])
    saved = st.session_state.get(key, {})
    def select(label, options, setting, default=None):
        options = [None] + options
        current = saved.get(setting, default)
        if current not in options:
            current = None
        return st.selectbox(label, options, index=options.index(current), format_func=lambda v: labels.get(v, 'None'))
    with st.expander('Choose analysis and filters', expanded=True):
        left, middle, right = st.columns(3)
        with left:
            preferred = next((c for c in numeric if labels[c].lower() in ['sales', 'revenue']), numeric[0] if numeric else None)
            metric = select('Numeric measure', numeric, 'metric', preferred)
        with middle:
            category = select('Compare by', text, 'category', text[0] if text else None)
        with right:
            date_column = select('Date / time field', dates, 'date_column', dates[0] if dates else None)
        aggregations = ['Sum', 'Mean', 'Median', 'Minimum', 'Maximum']
        aggregation = st.selectbox('Aggregation', aggregations, index=aggregations.index(saved.get('aggregation', 'Sum')),
                                   help='Choose the operation appropriate to your field. No units or business meaning are assumed.')
        selected_values, date_range = [], None
        if category:
            values = sorted(data[category].dropna().unique().tolist())
            if data[category].isna().any():
                values.append(None)
            if len(values) <= 2000:
                defaults = saved.get('values', []) if category == saved.get('category') else []
                selected_values = st.multiselect(f'Filter {labels[category]} (empty = all)', values,
                                                 default=[v for v in defaults if v in values],
                                                 format_func=lambda v: '(Missing)' if v is None else str(v))
                if selected_values:
                    mask = data[category].isin([v for v in selected_values if v is not None])
                    if None in selected_values:
                        mask |= data[category].isna()
                    data = data.loc[mask]
            else:
                st.caption('This comparison field has over 2,000 distinct values. Choose a lower-cardinality field for categorical filtering.')
        if date_column and data[date_column].notna().any():
            lower, upper = data[date_column].min().date(), data[date_column].max().date()
            previous = saved.get('date_range') if date_column == saved.get('date_column') else None
            default = previous if previous and len(previous) == 2 and lower <= previous[0] <= previous[1] <= upper else (lower, upper)
            date_range = st.date_input('Date range', value=default, min_value=lower, max_value=upper)
            if len(date_range) != 2:
                st.info('Select both dates to continue.')
                st.stop()
            st.caption('Applying a date range excludes records with a missing date. Select None as the date field to include them.')
            mask = data[date_column].dt.date.between(*date_range)
            data = data.loc[mask]
    filters = dict(metric=metric, category=category, date_column=date_column, aggregation=aggregation,
                   values=selected_values, date_range=date_range)
    st.session_state[key] = filters
    if data.empty:
        st.info('No rows match these filters. Clear a selection or widen the date range.')
        st.stop()
    return data, summarize(data, columns, metric, category, date_column, aggregation), filters, labels


def cards(result):
    columns = st.columns(3)
    for i, (label, value) in enumerate(result['kpis'].items()):
        formatted = 'N/A' if pd.isna(value) else f'{value:,}' if isinstance(value, int) else f'{value:,.4f}'
        columns[i % 3].metric(label, formatted)


def draw_chart(draw):
    sns.set_theme(style='whitegrid')
    fig, ax = plt.subplots(figsize=(8, 3.6))
    try:
        draw(ax)
        sns.despine(ax=ax)
        fig.tight_layout()
        st.pyplot(fig)
    finally:
        plt.close(fig)


def dashboard_page():
    st.title('Data Dashboard')
    st.write('Choose a dataset and analyse its actual measures, categories and dates.')
    try:
        dataset = pick_dataset(allow_delete=True)
        data, result, filters, labels = analysis_selection(dataset)
        cards(result)
        measure = f"{filters['aggregation']} of {labels[filters['metric']]}" if filters['metric'] else 'Row count'
        if not result['trend'].empty:
            st.subheader('Monthly trend · ' + measure)
            def line(ax):
                ax.plot(result['trend'].Period, result['trend'].Value, color='#0f766e', marker='o')
                ax.tick_params(axis='x', rotation=25)
                ax.set_ylabel(measure)
            draw_chart(line)
        if not result['groups'].empty:
            st.subheader('Top categories · ' + measure)
            group = result['groups'].head(10).copy()
            category = filters['category']
            group[category] = group[category].fillna('(Missing)').astype(str).str.slice(0, 70)
            def bar(ax):
                ax.barh(range(len(group)), group.Value, color='#0f766e')
                ax.set_yticks(range(len(group)), group[category])
                ax.invert_yaxis()
                ax.set_xlabel(measure)
            draw_chart(bar)
            with st.expander('All category results'):
                st.dataframe(result['groups'].rename(columns=labels), width='stretch')
        if filters['metric'] and data[filters['metric']].notna().any():
            st.subheader('Distribution · ' + labels[filters['metric']])
            draw_chart(lambda ax: ax.hist(data[filters['metric']].dropna(), bins=25, color='#0f766e', edgecolor='white'))
        if not filters['metric']:
            st.info('No numeric measure selected. Row counts, category frequencies and data quality remain available.')
        st.subheader('Findings')
        for finding in result['findings']:
            st.write('• ' + finding)
        st.subheader('Data quality')
        st.dataframe(result['quality'], width='stretch', hide_index=True)
        with st.expander('Numeric statistics'):
            st.dataframe(result['numeric'], width='stretch', hide_index=True)
        with st.expander('Filtered data'):
            st.dataframe(display_columns(data, dataset['columns']), width='stretch', hide_index=True)
    except DatabaseError as exc:
        migration_hint(exc)


def reports_page():
    st.title('Download Report')
    try:
        dataset = pick_dataset()
        data, result, filters, labels = analysis_selection(dataset)
        cards(result)
        a, b, c = st.columns(3)
        a.download_button('Filtered data · CSV', csv_bytes(display_columns(data, dataset['columns'])), 'filtered_dataset.csv', 'text/csv')
        b.download_button('Summary · Excel', export_summary(dataset, result, filters), 'dataset_summary.xlsx',
                          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        c.download_button('Findings · Text', export_findings(dataset, result, filters), 'dataset_findings.txt', 'text/plain')
        for finding in result['findings']:
            st.write('• ' + finding)
    except DatabaseError as exc:
        migration_hint(exc)


def chatbot_page():
    st.title('Ask Elevate')
    try:
        dataset = pick_dataset()
    except DatabaseError as exc:
        migration_hint(exc)
        return
    st.caption('Questions use the selected dataset, not dashboard filters. Only the schema and recent questions/SQL '
               'are sent to Groq. Result rows remain local. Conversation context is separate for each dataset.')
    with st.expander('Available fields and SQL names'):
        st.dataframe(pd.DataFrame(dataset['columns']), width='stretch', hide_index=True)
    st.write('Try “How many rows are there?”, “Summarize [numeric field]”, or “Compare [measure] by [category]”.')
    key = 'dataset_chat_' + str(dataset['dataset_id'])
    session_key = key + '_session'
    st.session_state.setdefault(key, [])
    st.session_state.setdefault(session_key, str(uuid.uuid4()))
    if st.button('Clear this conversation'):
        st.session_state[key] = []
        st.session_state[session_key] = str(uuid.uuid4())
        st.rerun()
    def show(item):
        with st.chat_message('assistant'):
            st.write(item['answer'])
            with st.expander('Generated SQL and parameters'):
                st.code(item['sql'], language='sql')
                st.json(item['params'])
                st.caption(f"The dataset source is bound by the application to dataset #{dataset['dataset_id']}; the model cannot switch datasets.")
            st.dataframe(item['results'], width='stretch', hide_index=True)
    for item in st.session_state[key]:
        with st.chat_message('user'):
            st.write(item['question'])
        show(item)
    if question := st.chat_input('Ask about a field in this dataset…', max_chars=1500):
        with st.chat_message('user'):
            st.write(question)
        try:
            with st.spinner('Querying the selected dataset in MySQL…'):
                sql, params = generate_query(question, st.session_state[key], dataset)
                result = execute_select(sql, params, dataset)
                answer = explain_results(result)
            item = dict(question=question, sql=sql, params=params, results=result, answer=answer)
            st.session_state[key] = (st.session_state[key] + [item])[-10:]
            show(item)
            try:
                save_chat(st.session_state[session_key], f"[Dataset {dataset['dataset_id']}] {question}", sql, params, answer)
            except DatabaseError:
                st.warning('The answer succeeded, but saving its conversation log failed.')
        except (ChatbotError, DatabaseError, ValueError) as exc:
            st.error(str(exc))
