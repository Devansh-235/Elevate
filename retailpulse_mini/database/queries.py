"""Parameterized application queries and atomic, idempotent imports."""
import json
from decimal import Decimal

import pandas as pd

from database.connection import DatabaseError, connection


def fetch_frame(sql, params=()):
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql, tuple(params))
            rows = cursor.fetchall()
            columns = cursor.column_names
            return pd.DataFrame(rows, columns=columns)
        finally:
            cursor.close()


def filter_options():
    bounds = fetch_frame('SELECT MIN(order_date) AS first_date, MAX(order_date) AS last_date FROM orders')
    categories = fetch_frame('SELECT DISTINCT category FROM products ORDER BY category')['category'].tolist()
    locations = fetch_frame('SELECT DISTINCT city, region FROM orders ORDER BY region, city')
    return bounds.iloc[0].to_dict(), categories, locations


def sales_data(start, end, categories=(), cities=(), regions=()):
    conditions = ['order_date BETWEEN %s AND %s']
    params = [start, end]
    for column, values in [('category', categories), ('city', cities), ('region', regions)]:
        if values:
            conditions.append(f"{column} IN ({','.join(['%s'] * len(values))})")
            params.extend(values)
    return fetch_frame('SELECT * FROM retail_sales WHERE ' + ' AND '.join(conditions)
                       + ' ORDER BY order_date, order_id, product_id', params)


def upload_history():
    return fetch_frame('SELECT file_name, inserted_records, invalid_records, uploaded_at '
                       'FROM uploaded_files ORDER BY upload_id DESC LIMIT 10')


def insert_cleaned(frame, file_name, file_hash, total_records, invalid_records):
    """All-or-nothing. Existing order lines or conflicting master data abort import.

    No-op upserts acquire row locks before comparison, including concurrent uploads.
    Existing customer/product/order metadata is never silently overwritten.
    """
    if frame.empty:
        raise DatabaseError('There are no valid rows to insert.')
    with connection() as conn:
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()
            cursor.execute('SELECT upload_id FROM uploaded_files WHERE file_hash = %s', (file_hash,))
            if cursor.fetchone():
                raise DatabaseError('This exact file was already imported. No records were added.')
            cursor.execute(
                'INSERT INTO uploaded_files (file_name,file_hash,total_records,valid_records,'
                'invalid_records,inserted_records) VALUES (%s,%s,%s,%s,%s,%s)',
                (file_name[:255], file_hash, total_records, len(frame), invalid_records, len(frame)))
            upload_id = cursor.lastrowid

            specs = [
                ('customers', ['customer_id', 'customer_name'], ['Customer ID', 'Customer Name']),
                ('products', ['product_id', 'product_name', 'category'], ['Product ID', 'Product Name', 'Category']),
                ('orders', ['order_id', 'order_date', 'customer_id', 'city', 'region'],
                 ['Order ID', 'Order Date', 'Customer ID', 'City', 'Region']),
            ]
            for table, columns, source in specs:
                for values in frame[source].drop_duplicates().sort_values(source[0]).itertuples(index=False, name=None):
                    values = tuple(v.date() if isinstance(v, pd.Timestamp) else v for v in values)
                    key = columns[0]
                    cursor.execute(
                        f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join(['%s']*len(columns))}) "
                        f'ON DUPLICATE KEY UPDATE {key} = {key}', values)
                    cursor.execute(f"SELECT {','.join(columns)} FROM {table} WHERE {key} = %s FOR UPDATE", (values[0],))
                    stored = cursor.fetchone()
                    if tuple(stored[c] for c in columns) != values:
                        raise DatabaseError(f'Conflicting {table} metadata for {values[0]}. '
                                            'Correct the source file; the entire import was rolled back.')

            items = []
            for row in frame.to_dict('records'):
                items.append((row['Order ID'], row['Product ID'], int(row['Quantity']),
                              Decimal(str(row['Unit Price'])), Decimal(str(row['Cost Price'])),
                              Decimal(str(row['Discount'])), upload_id))
            cursor.executemany(
                'INSERT INTO order_items (order_id,product_id,quantity,unit_price,cost_price,discount,upload_id) '
                'VALUES (%s,%s,%s,%s,%s,%s,%s)', items)
            conn.commit()
            return len(items)
        except Exception as exc:
            conn.rollback()
            if getattr(exc, 'errno', None) == 1062:
                raise DatabaseError('This file contains order lines already stored in MySQL '
                                    '(same Order ID and Product ID), or the file was imported concurrently. '
                                    'Nothing was added. Remove existing lines and upload again.') from exc
            raise
        finally:
            cursor.close()


def save_chat(session_id, question, sql, params, answer):
    with connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute('INSERT INTO chat_history (session_id,question,generated_sql,query_parameters,answer) '
                           'VALUES (%s,%s,%s,%s,%s)',
                           (session_id, question, sql, json.dumps(params), answer))
            conn.commit()
        finally:
            cursor.close()
