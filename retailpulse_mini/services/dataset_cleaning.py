"""Schema discovery and user-controlled cleaning for flat tabular datasets."""
import csv
import hashlib
import json
import re
from io import BytesIO, StringIO

import numpy as np
import pandas as pd

MAX_ROWS, MAX_COLUMNS, MAX_BYTES = 100000, 150, 20 * 1024 * 1024
KINDS = ['Text', 'Number', 'Date']


def read_table(content, filename, sheet=0, header_row=1, separator=','):
    if len(content) > MAX_BYTES:
        raise ValueError('Use a file smaller than 20 MB.')
    if filename.lower().endswith('.xlsx'):
        raw = pd.read_excel(BytesIO(content), sheet_name=sheet, header=None, skiprows=header_row-1,
                            nrows=MAX_ROWS+2, dtype=str, keep_default_na=False, engine='openpyxl')
    elif filename.lower().endswith('.csv'):
        raw = pd.read_csv(BytesIO(content), header=None, skiprows=header_row-1, nrows=MAX_ROWS+2,
                          dtype=str, keep_default_na=False, encoding='utf-8-sig', sep=separator)
    else:
        raise ValueError('Choose a CSV or .xlsx workbook. PDFs, images and legacy .xls files are not tabular uploads.')
    if len(raw) < 2:
        raise ValueError('Choose a header row with at least one data row below it.')
    names = [str(v).strip() if pd.notna(v) else '' for v in raw.iloc[0]]
    if not all(names) or len(set(names)) != len(names):
        raise ValueError('The selected header row needs nonempty, unique column names. Select the correct header row.')
    if len(names) > MAX_COLUMNS or any(len(n) > 180 for n in names):
        raise ValueError('Use at most 150 columns, with column names no longer than 180 characters.')
    frame = raw.iloc[1:].copy().reset_index(drop=True)
    frame.columns = names
    if len(frame) > MAX_ROWS:
        raise ValueError('Use at most 100,000 rows per dataset.')
    return frame


def discover_columns(frame):
    columns, seen = [], set()
    for name in frame:
        base = 'c_' + (re.sub('[^a-z0-9]+', '_', str(name).lower()).strip('_') or 'column')[:45]
        alias, counter = base, 2
        while alias in seen:
            alias = f'{base}_{counter}'
            counter += 1
        seen.add(alias)
        values = frame[name].dropna().astype(str).str.strip()
        values = values[values.ne('')]
        kind = 'Text'
        identifier = bool(re.search(r'(^|[ _])(id|code|zip|pin|phone|year)($|[ _])', str(name), re.I)) or str(name).lower().endswith('id')
        leading_zero = values.str.match(r'^0\d+$').any()
        if len(values) and not identifier and not leading_zero:
            numeric = pd.to_numeric(values, errors='coerce')
            if numeric.notna().all() and np.isfinite(numeric).all():
                kind = 'Number'
            elif values.str.match(r'^\d{4}-\d{2}-\d{2}([ T].*)?$').all():
                if pd.to_datetime(values, format='ISO8601', errors='coerce').notna().all():
                    kind = 'Date'
        columns.append({'name': name, 'sql_name': alias, 'kind': kind})
    return columns


def clean_table(raw, columns, drop_duplicates=False, invalid_policy='Reject rows', date_format='ISO8601', header_row=1):
    if [c['name'] for c in columns] != list(raw.columns) or any(c['kind'] not in KINDS for c in columns):
        raise ValueError('Column settings do not match the uploaded dataset.')
    clean = pd.DataFrame(index=raw.index)
    reasons = pd.Series('', index=raw.index)
    warnings = []
    blank = raw.map(lambda v: pd.isna(v) or (isinstance(v, str) and not v.strip()))
    reasons.loc[blank.all(axis=1)] += 'Empty row; '
    for column in columns:
        name, alias, kind = column['name'], column['sql_name'], column['kind']
        values = raw[name].where(~blank[name], None)
        if kind == 'Number':
            parsed = pd.to_numeric(values, errors='coerce')
            bad = values.notna() & (parsed.isna() | ~np.isfinite(parsed))
            clean[alias] = parsed.where(np.isfinite(parsed), np.nan)
        elif kind == 'Date':
            # Date columns are timezone-naive; users can retain timestamps with offsets as text.
            parsed = pd.to_datetime(values, format=date_format, errors='coerce')
            if not hasattr(parsed, 'dt') or getattr(parsed.dt, 'tz', None) is not None:
                raise ValueError(f'{name}: timezone-aware or mixed-timezone timestamps should be imported as Text.')
            bad = values.notna() & parsed.isna()
            clean[alias] = parsed
        else:
            clean[alias] = values.map(lambda v: str(v).strip() if pd.notna(v) else None)
            bad = clean[alias].fillna('').str.len().gt(2048)
        if bad.any():
            if invalid_policy == 'Set invalid cells to missing':
                clean.loc[bad, alias] = None
                warnings.append(f'{name}: {int(bad.sum())} invalid cells set to missing.')
            else:
                reasons.loc[bad] += f'Invalid {kind.lower()} value in {name}; '
    duplicates = clean.duplicated(keep='first')
    if drop_duplicates:
        reasons.loc[duplicates] += 'Duplicate row; '
    valid = clean.loc[reasons.eq('')].copy()
    rejected = raw.loc[reasons.ne('')].copy()
    # Collision-safe diagnostic headings, without overwriting any source column.
    reason_name, row_name = 'Rejection Reason', 'Source Row'
    while reason_name in rejected:
        reason_name = '_' + reason_name
    while row_name in rejected:
        row_name = '_' + row_name
    rejected[row_name] = rejected.index + header_row + 1
    rejected[reason_name] = reasons.loc[rejected.index].str.rstrip('; ')
    quality = {'Rows': len(raw), 'Accepted': len(valid), 'Rejected': len(rejected),
               'Duplicate rows': int(duplicates.sum()), 'Missing cells': int(blank.sum().sum())}
    return valid, rejected, quality, warnings


def fingerprint(content, sheet, header, columns, options):
    config = json.dumps([sheet, header, columns, options], sort_keys=True).encode()
    return hashlib.sha256(content + config).hexdigest()


def display_columns(frame, columns):
    return frame.rename(columns={c['sql_name']: c['name'] for c in columns})
