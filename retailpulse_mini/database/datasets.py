"""Generic MySQL dataset storage; no per-upload DDL or arbitrary identifiers."""
import json
import re

import pandas as pd

from database.connection import connection, DatabaseError
from database.queries import fetch_frame

TYPES = {'Text': 'VARCHAR(2048)', 'Number': 'DOUBLE', 'Date': 'DATETIME'}


def checked_columns(columns):
    if not isinstance(columns, list) or not 1 <= len(columns) <= 150:
        raise ValueError('Invalid dataset schema.')
    seen = set()
    for c in columns:
        name = c['sql_name']
        if not re.fullmatch(r'c_[a-z0-9_]{1,60}', name) or name in seen or c['kind'] not in TYPES:
            raise ValueError('Invalid dataset column metadata.')
        seen.add(name)
    return columns


def list_datasets():
    return fetch_frame('SELECT dataset_id, name, row_count, created_at FROM datasets ORDER BY dataset_id DESC')


def delete_dataset(dataset_id):
    """Delete exactly one dataset and its rows, atomically; never execute model SQL."""
    dataset_id = int(dataset_id)
    with connection() as conn:
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            cursor.execute('SELECT dataset_id FROM datasets WHERE dataset_id = %s FOR UPDATE', (dataset_id,))
            if cursor.fetchone() is None:
                raise DatabaseError('This dataset was already deleted. Refresh the dataset list.')
            cursor.execute('DELETE FROM dataset_rows WHERE dataset_id = %s', (dataset_id,))
            removed = cursor.rowcount
            cursor.execute('DELETE FROM datasets WHERE dataset_id = %s', (dataset_id,))
            conn.commit()
            return removed
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()


def get_dataset(dataset_id):
    frame = fetch_frame('SELECT * FROM datasets WHERE dataset_id = %s', (int(dataset_id),))
    if frame.empty:
        raise DatabaseError('This dataset no longer exists. Select another dataset.')
    record = frame.iloc[0].to_dict()
    record['columns'] = checked_columns(json.loads(record['columns_json']))
    return record


def dataset_source(columns):
    checked_columns(columns)
    definitions = ', '.join(f"`{c['sql_name']}` {TYPES[c['kind']]} PATH '$.{c['sql_name']}' NULL ON EMPTY ERROR ON ERROR" for c in columns)
    return f"(SELECT jt.* FROM dataset_rows r JOIN JSON_TABLE(r.payload, '$' COLUMNS ({definitions})) AS jt WHERE r.dataset_id = %s) AS dataset"


def load_dataset(dataset):
    frame = fetch_frame('SELECT * FROM ' + dataset_source(dataset['columns']), (int(dataset['dataset_id']),))
    for c in dataset['columns']:
        if c['kind'] == 'Date':
            frame[c['sql_name']] = pd.to_datetime(frame[c['sql_name']], errors='raise')
        elif c['kind'] == 'Number':
            frame[c['sql_name']] = pd.to_numeric(frame[c['sql_name']], errors='raise')
    return frame


def save_dataset(frame, columns, name, filename, digest, rejected_count):
    checked_columns(columns)
    if frame.empty or not name.strip():
        raise ValueError('Give the dataset a name and include at least one accepted row.')
    if list(frame.columns) != [c['sql_name'] for c in columns]:
        raise ValueError('Stored schema does not match accepted columns.')
    with connection() as conn:
        cursor = conn.cursor()
        try:
            conn.start_transaction()
            cursor.execute('SELECT dataset_id FROM datasets WHERE import_hash = %s', (digest,))
            existing = cursor.fetchone()
            if existing:
                conn.rollback()
                return int(existing[0]), False
            cursor.execute('INSERT INTO datasets (name,file_name,import_hash,columns_json,row_count,rejected_count) '
                           'VALUES (%s,%s,%s,%s,%s,%s)',
                           (name.strip()[:180], filename[:255], digest, json.dumps(columns), len(frame), rejected_count))
            dataset_id = cursor.lastrowid
            batch = []
            for row in frame.to_dict('records'):
                payload = {k: (None if pd.isna(v) else v.isoformat(sep=' ') if isinstance(v, pd.Timestamp) else v) for k, v in row.items()}
                batch.append((dataset_id, json.dumps(payload, ensure_ascii=False, allow_nan=False)))
                if len(batch) == 250:
                    cursor.executemany('INSERT INTO dataset_rows (dataset_id,payload) VALUES (%s,%s)', batch)
                    batch = []
            if batch:
                cursor.executemany('INSERT INTO dataset_rows (dataset_id,payload) VALUES (%s,%s)', batch)
            conn.commit()
            return int(dataset_id), True
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
