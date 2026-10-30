import json
import unittest
from io import BytesIO
from unittest.mock import patch, MagicMock

import pandas as pd
from openpyxl import load_workbook

from services.dataset_cleaning import read_table, discover_columns, clean_table
from services.dataset_analytics import summarize
from services.dataset_reports import export_summary
from services.chatbot_service import validate_select, execute_select, ChatbotError


class GenericTests(unittest.TestCase):
    def test_domains_negative_missing_and_identifiers(self):
        raw = read_table(b'Employee ID,Department,Change,Started\n001,HR,-2.5,2024-01-01\n002,IT,,2024-02-01\n', 'hr.csv')
        columns = discover_columns(raw)
        self.assertEqual([c['kind'] for c in columns], ['Text', 'Text', 'Number', 'Date'])
        valid, rejected, quality, _ = clean_table(raw, columns)
        self.assertEqual(valid.c_employee_id.tolist(), ['001', '002'])
        self.assertEqual(valid.c_change.iloc[0], -2.5)
        self.assertTrue(pd.isna(valid.c_change.iloc[1]))
        self.assertEqual(len(rejected), 0)

    def test_invalid_policy_duplicates_and_duplicate_headers(self):
        raw = read_table(b'Name,Value\nA,1\nA,1\nB,bad\n', 'x.csv')
        columns = discover_columns(raw)
        columns[1]['kind'] = 'Number'
        good, bad, _, _ = clean_table(raw, columns, drop_duplicates=True)
        self.assertEqual((len(good), len(bad)), (1, 2))
        good, bad, _, notes = clean_table(raw, columns, invalid_policy='Set invalid cells to missing')
        self.assertEqual(len(good), 3)
        self.assertTrue(pd.isna(good.iloc[2].c_value))
        self.assertTrue(notes)
        with self.assertRaises(ValueError):
            read_table(b'A,A\n1,2\n', 'duplicate.csv')

    def test_header_sheet_and_no_numeric_data(self):
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            pd.DataFrame([['Report', None], ['Person', 'Status'], ['A', 'Open'], ['B', 'Closed']]).to_excel(writer, sheet_name='Custom', header=False, index=False)
        raw = read_table(buffer.getvalue(), 'x.xlsx', sheet='Custom', header_row=2)
        columns = discover_columns(raw)
        frame, _, _, _ = clean_table(raw, columns)
        result = summarize(frame, columns, category='c_status')
        self.assertEqual(result['kpis']['Rows'], 2)
        self.assertEqual(result['groups'].Value.sum(), 2)
        self.assertTrue(result['numeric'].empty)
        workbook = load_workbook(BytesIO(export_summary({'dataset_id': 1, 'name': 'Text', 'columns': columns}, result, {})))
        self.assertIn('Data quality', workbook.sheetnames)

    def test_safe_column_names_and_dataset_sql_isolation(self):
        raw = pd.DataFrame({'DROP TABLE x;': ['a'], 'A B': ['1'], 'A-B': ['2']})
        columns = discover_columns(raw)
        names = [c['sql_name'] for c in columns]
        self.assertEqual(len(names), len(set(names)))
        for name in names:
            self.assertRegex(name, r'^c_[a-z0-9_]+$')
        self.assertIn('LIMIT', validate_select('SELECT COUNT(*) AS n FROM dataset', [], names, 'dataset'))
        for sql in ['SELECT * FROM retail_sales', 'SELECT * FROM dataset_rows',
                    'SELECT * FROM dataset WHERE dataset_id = 99', 'SELECT SUM(revenue) FROM dataset']:
            with self.assertRaises(ChatbotError):
                validate_select(sql, [], names, 'dataset')

    def test_parameter_order_and_empty_numeric_sum(self):
        columns = [{'name': 'Date', 'sql_name': 'c_date', 'kind': 'Date'},
                   {'name': 'Amount', 'sql_name': 'c_amount', 'kind': 'Number'}]
        dataset = {'dataset_id': 17, 'columns': columns}
        with patch('services.chatbot_service.connection') as context:
            conn = context.return_value.__enter__.return_value
            cursor = conn.cursor.return_value
            cursor.fetchmany.return_value = []
            cursor.column_names = ['month', 'amount']
            execute_select('SELECT DATE_FORMAT(c_date, %s) AS month, SUM(c_amount) AS amount FROM dataset WHERE c_amount > %s GROUP BY month', ['%Y-%m', 0], dataset)
            sql, params = cursor.execute.call_args_list[1].args
            self.assertEqual(params, ('%Y-%m', 17, 0))
            self.assertIn('JSON_TABLE', sql)
        frame = pd.DataFrame({'c_date': pd.to_datetime(['2024-01-01']), 'c_amount': [float('nan')]})
        result = summarize(frame, columns, metric='c_amount')
        self.assertTrue(pd.isna(result['kpis']['Sum of Amount']))
