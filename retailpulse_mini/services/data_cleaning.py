"""Strict row validation with original rejected values and human-readable reasons."""
from io import BytesIO

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ['Order ID', 'Order Date', 'Customer ID', 'Customer Name', 'Product ID',
                    'Product Name', 'Category', 'Quantity', 'Unit Price', 'Cost Price',
                    'Discount', 'City', 'Region']
TEXT_LIMITS = {'Order ID': 64, 'Customer ID': 64, 'Product ID': 64,
               'Customer Name': 160, 'Product Name': 160, 'Category': 100, 'City': 100, 'Region': 100}
DATE_FORMATS = {'ISO (YYYY-MM-DD)': '%Y-%m-%d', 'Day first (DD/MM/YYYY)': '%d/%m/%Y',
                'Month first (MM/DD/YYYY)': '%m/%d/%Y'}


def read_upload(content, name):
    if len(content) > 20 * 1024 * 1024:
        raise ValueError('Please use a file no larger than 20 MB.')
    try:
        if name.lower().endswith('.csv'):
            # Preserve leading zeroes in identifiers and literal names like "NA".
            frame = pd.read_csv(BytesIO(content), dtype=str, keep_default_na=False, encoding='utf-8-sig')
        elif name.lower().endswith('.xlsx'):
            frame = pd.read_excel(BytesIO(content), engine='openpyxl', dtype=str, keep_default_na=False)
        else:
            raise ValueError('Choose a UTF-8 CSV or .xlsx file. Legacy .xls is not supported by OpenPyXL.')
    except Exception as exc:
        raise ValueError(f'Cannot read this file: {exc}') from exc
    frame.columns = frame.columns.astype(str).str.strip()
    if frame.columns.duplicated().any():
        raise ValueError('Column names must be unique after trimming whitespace.')
    if len(frame) > 100000:
        raise ValueError('This mini application supports at most 100,000 rows per file.')
    if frame.empty:
        raise ValueError('The file has no sales records.')
    return frame


def clean_data(raw, date_format='%Y-%m-%d'):
    missing = [c for c in REQUIRED_COLUMNS if c not in raw.columns]
    if missing:
        raise ValueError('Missing required columns: ' + ', '.join(missing))
    frame = raw[REQUIRED_COLUMNS].copy().reset_index(drop=True)
    original = frame.copy()
    reasons = pd.Series('', index=frame.index)

    def reject(mask, reason):
        reasons.loc[mask.fillna(True) if hasattr(mask, 'fillna') else mask] += reason + '; '

    for col in REQUIRED_COLUMNS:
        blank = frame[col].isna() | frame[col].astype(str).str.strip().eq('')
        reject(blank, f'Missing {col}')
    for col, limit in TEXT_LIMITS.items():
        frame[col] = frame[col].fillna('').astype(str).str.strip()
        reject(frame[col].str.len().gt(limit), f'{col} exceeds {limit} characters')
        reject(frame[col].str.contains(r'[\x00-\x1f]', regex=True), f'Control character in {col}')

    dates = frame['Order Date'].astype(str).str.strip()
    # Excel date cells are read as ISO timestamps even if their display format differs.
    excel_dates = dates.str.match(r'^\d{4}-\d{2}-\d{2} 00:00:00$')
    parsed = pd.to_datetime(dates, format=date_format, errors='coerce')
    parsed.loc[excel_dates] = pd.to_datetime(dates.loc[excel_dates], format='%Y-%m-%d %H:%M:%S', errors='coerce')
    frame['Order Date'] = parsed.dt.normalize()
    reject(parsed.isna(), 'Invalid date or wrong selected date format')

    for col in ['Quantity', 'Unit Price', 'Cost Price', 'Discount']:
        values = pd.to_numeric(frame[col], errors='coerce')
        frame[col] = values
        reject(values.isna() | ~np.isfinite(values), f'{col} must be a finite number')
        reject(values.lt(0), f'Negative {col}')
    quantity = frame['Quantity']
    reject(quantity.le(0) | quantity.gt(1000000) | quantity.mod(1).ne(0), 'Quantity must be a whole number from 1 to 1000000')
    reject(frame['Discount'].gt(1), 'Discount must be a fraction between 0 and 1')
    for col, digits in [('Unit Price', 2), ('Cost Price', 2), ('Discount', 5)]:
        value = frame[col]
        reject(~np.isclose(value, value.round(digits), rtol=0, atol=1e-9, equal_nan=True),
               f'{col} supports at most {digits} decimal places')
        if col != 'Discount':
            reject(value.gt(9999999999.99), f'{col} exceeds database precision')

    # Duplicates are evaluated only among otherwise-valid normalized rows.
    eligible = reasons.eq('')
    duplicates = pd.Series(False, index=frame.index)
    duplicates.loc[eligible] = frame.loc[eligible].duplicated(keep='first')
    reject(duplicates, 'Duplicate record')
    eligible = reasons.eq('')
    conflicts = frame.loc[eligible].duplicated(['Order ID', 'Product ID'], keep=False)
    reject(conflicts.reindex(frame.index, fill_value=False), 'Conflicting order/product line')

    # Validate the full set before rejecting any dimension conflicts, so no group slips through.
    eligible_frame = frame.loc[reasons.eq('')]
    for key, attrs in [('Customer ID', ['Customer Name']),
                       ('Product ID', ['Product Name', 'Category']),
                       ('Order ID', ['Order Date', 'Customer ID', 'City', 'Region'])]:
        counts = eligible_frame.groupby(key)[attrs].nunique(dropna=False)
        bad_ids = counts.index[counts.gt(1).any(axis=1)]
        reject(frame[key].isin(bad_ids), f'Inconsistent metadata for {key}')

    valid = frame.loc[reasons.eq('')].copy()
    valid['Quantity'] = valid['Quantity'].astype(int)
    valid['Revenue'] = valid['Quantity'] * valid['Unit Price'] * (1 - valid['Discount'])
    valid['Profit'] = valid['Revenue'] - valid['Quantity'] * valid['Cost Price']
    rejected = original.loc[reasons.ne('')].copy()
    rejected.insert(0, 'Source Row', rejected.index + 2)
    rejected['Rejection Reason'] = reasons.loc[reasons.ne('')].str.rstrip('; ')
    summary = {'total': len(frame), 'valid': len(valid), 'invalid': len(rejected),
               'duplicates': int(duplicates.sum()),
               'missing_cells': int(original.isna().sum().sum() +
                                    original.map(lambda v: isinstance(v, str) and not v.strip()).sum().sum())}
    return valid, rejected, summary
