"""Run with: python -m unittest discover -s tests -v"""
import unittest
import json
import os
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from openpyxl import load_workbook

from services.analytics import analyze, business_findings
from services.chatbot_service import ChatbotError, execute_select, generate_query, validate_select
from services.data_cleaning import clean_data, read_upload
from services.report_generator import csv_bytes, findings_text, kpi_excel

ROOT = Path(__file__).resolve().parents[1]


def example():
    return pd.DataFrame([{'Order ID': '001', 'Order Date': '2025-01-01', 'Customer ID': 'C1',
                          'Customer Name': 'Alex', 'Product ID': 'P1', 'Product Name': 'Tea',
                          'Category': 'Grocery', 'Quantity': '2', 'Unit Price': '100',
                          'Cost Price': '60', 'Discount': '0.10', 'City': 'Delhi', 'Region': 'North'}])


class CleaningTests(unittest.TestCase):
    def test_sample_and_formulas(self):
        path = ROOT / 'sample_data/retail_sales.csv'
        raw = read_upload(path.read_bytes(), path.name)
        valid, rejected, stats = clean_data(raw)
        self.assertEqual((len(valid), len(rejected), stats['total']), (5000, 0, 5000))
        self.assertEqual(valid['Order ID'].nunique(), 2500)
        valid, _, _ = clean_data(example())
        self.assertEqual(valid.iloc[0]['Revenue'], 180)
        self.assertEqual(valid.iloc[0]['Profit'], 60)

    def test_invalid_values(self):
        for column, value in [('Quantity', '-1'), ('Quantity', '1.5'), ('Quantity', '0'),
                              ('Unit Price', '-1'), ('Cost Price', '-2'), ('Discount', '-.1'),
                              ('Discount', '10'), ('Unit Price', 'inf'), ('Cost Price', '1.123'),
                              ('Order Date', '2025-02-30'), ('Customer Name', ''), ('Region', None)]:
            with self.subTest(column=column, value=value):
                frame = example()
                frame.loc[0, column] = value
                valid, rejected, _ = clean_data(frame)
                self.assertTrue(valid.empty)
                self.assertEqual(len(rejected), 1)
                self.assertTrue(rejected.iloc[0]['Rejection Reason'])

    def test_dates_duplicates_and_conflicts(self):
        raw = example()
        valid, rejected, stats = clean_data(pd.concat([raw, raw], ignore_index=True))
        self.assertEqual((len(valid), len(rejected), stats['duplicates']), (1, 1, 1))
        other = raw.copy()
        other.loc[0, 'Quantity'] = '3'
        self.assertEqual(len(clean_data(pd.concat([raw, other]))[1]), 2)
        other.loc[0, 'Order ID'] = '002'
        other.loc[0, 'Customer Name'] = 'Different'
        self.assertEqual(len(clean_data(pd.concat([raw, other]))[1]), 2)
        raw.loc[0, 'Order Date'] = '02/03/2025'
        self.assertEqual(clean_data(raw, '%d/%m/%Y')[0].iloc[0]['Order Date'].date(), date(2025, 3, 2))

    def test_missing_columns_and_excel(self):
        with self.assertRaises(ValueError):
            clean_data(example().drop(columns='Region'))
        output = BytesIO()
        frame = example()
        frame['Order Date'] = pd.to_datetime(frame['Order Date'])
        frame.to_excel(output, index=False, engine='openpyxl')
        raw = read_upload(output.getvalue(), 'test.xlsx')
        self.assertEqual(clean_data(raw)[0].iloc[0]['Order ID'], '001')


class SqlTests(unittest.TestCase):
    def test_valid_business_queries(self):
        samples = [
            ('SELECT SUM(revenue) AS total_revenue FROM retail_sales', []),
            ('SELECT product_name, SUM(profit) AS total_profit FROM retail_sales GROUP BY product_name ORDER BY total_profit DESC LIMIT 5', []),
            ('SELECT DATE_FORMAT(order_date, %s) AS month, SUM(revenue) AS sales FROM retail_sales GROUP BY month ORDER BY month', ['%Y-%m']),
            ('SELECT SUM(profit) / NULLIF(SUM(revenue),0) * 100 AS margin FROM retail_sales WHERE region = %s', ["North'; DROP TABLE orders; --"]),
            ('SELECT COUNT(DISTINCT order_id) AS orders_count FROM retail_sales WHERE order_date BETWEEN %s AND %s', ['2025-01-01', '2025-12-31']),
        ]
        for sql, params in samples:
            with self.subTest(sql=sql):
                self.assertIn('LIMIT', validate_select(sql, params))

    def test_dangerous_sql_blocked_before_connection(self):
        blocked = ['DELETE FROM retail_sales', 'SELECT * FROM customers',
                   'SELECT * FROM retail_sales; DROP TABLE orders',
                   'SELECT SLEEP(9) FROM retail_sales', 'SELECT LOAD_FILE(%s) FROM retail_sales',
                   'SELECT * INTO OUTFILE %s FROM retail_sales',
                   'SELECT * FROM retail_sales UNION SELECT * FROM customers',
                   'SELECT * FROM retail_sales /* comment */',
                   'SELECT @@version FROM retail_sales', 'SELECT * FROM retail_sales FOR UPDATE',
                   'SELECT * FROM retail_sales LIMIT 10000', 'SELECT * FROM retail_sales, customers',
                   'SELECT (SELECT COUNT(*) FROM customers) FROM retail_sales',
                   'SELECT * FROM information_schema.tables',
                   'SELECT schema_function(revenue) AS schema_function FROM retail_sales',
                   "SELECT * FROM retail_sales WHERE city = 'Delhi'",
                   'SELECT * FROM retail_sales WHERE city = %s']
        with patch('services.chatbot_service.connection') as connect:
            for sql in blocked:
                with self.subTest(sql=sql), self.assertRaises(ChatbotError):
                    execute_select(sql, [])
            connect.assert_not_called()


class AnalyticsReportTests(unittest.TestCase):
    def test_aggregation_exports_and_zero_revenue(self):
        valid, _, _ = clean_data(example())
        frame = valid.rename(columns=lambda c: c.lower().replace(' ', '_'))
        result = analyze(frame)
        self.assertEqual(result['kpis']['Total revenue'], 180)
        self.assertEqual(result['kpis']['Total profit'], 60)
        self.assertEqual(result['kpis']['Average order value'], 180)
        self.assertAlmostEqual(result['kpis']['Profit margin'], 100 / 3)
        filters = dict(dates=(date(2025, 1, 1), date(2025, 12, 31)), categories=[], cities=[], regions=[])
        workbook = load_workbook(BytesIO(kpi_excel(result, filters, 'INR')))
        self.assertEqual(workbook['KPI Summary']['B2'].value, 180)
        self.assertEqual(workbook.sheetnames, ['KPI Summary', 'Filters'])
        self.assertIn('Delhi', csv_bytes(frame).decode('utf-8-sig'))
        self.assertIn(b'MySQL', findings_text(business_findings(result), filters, 'INR'))
        frame['revenue'] = 0
        self.assertIsNone(analyze(frame)['kpis']['Profit margin'])
        self.assertIn("'=1+1", csv_bytes(pd.DataFrame({'name': ['=1+1']})).decode('utf-8-sig'))


class ChatGenerationTests(unittest.TestCase):
    def test_langchain_pipeline_and_bad_model_output(self):
        from langchain_core.messages import AIMessage
        from langchain_core.runnables import RunnableLambda
        payload = json.dumps({'sql': 'SELECT SUM(revenue) AS total_revenue FROM retail_sales', 'params': []})
        fake_model = RunnableLambda(lambda prompt: AIMessage(content=payload))
        with patch.dict(os.environ, {'GROQ_API_KEY': 'test-key'}):
            with patch('langchain_groq.ChatGroq', return_value=fake_model):
                sql, params = generate_query('What is the total revenue?', [])
                self.assertIn('SUM(revenue)', sql)
                self.assertEqual(params, [])
            bad_model = RunnableLambda(lambda prompt: AIMessage(content='not query JSON'))
            with patch('langchain_groq.ChatGroq', return_value=bad_model), self.assertRaises(ChatbotError):
                generate_query('What is the total revenue?', [])


if __name__ == '__main__':
    unittest.main()
