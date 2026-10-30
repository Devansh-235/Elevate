"""In-memory exports, with spreadsheet formula injection protection."""
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill


def spreadsheet_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def csv_bytes(frame):
    return frame.map(spreadsheet_safe).to_csv(index=False).encode('utf-8-sig')


def filter_description(filters):
    dates = filters['dates']
    return (f'Date range: {dates[0]} to {dates[1]}\n'
            f"Categories: {', '.join(filters['categories']) or 'All'}\n"
            f"Regions: {', '.join(filters['regions']) or 'All'}\n"
            f"Cities: {', '.join(filters['cities']) or 'All'}")


def kpi_excel(result, filters, currency):
    output = BytesIO()
    summary = pd.DataFrame([{'Metric': key, 'Value': value,
                             'Unit': '%' if key == 'Profit margin' else
                             ('count' if key in ['Total orders', 'Total customers'] else currency)}
                            for key, value in result['kpis'].items()])
    metadata = pd.DataFrame({'Report context': [filter_description(filters),
                            'Source: MySQL retail_sales view', 'N/A margin means zero revenue.',
                            'Average order value uses filtered revenue / distinct filtered orders.',
                            'Generated UTC: ' + datetime.now(timezone.utc).isoformat()]})
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        summary.to_excel(writer, sheet_name='KPI Summary', index=False, na_rep='N/A')
        metadata.map(spreadsheet_safe).to_excel(writer, sheet_name='Filters', index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = 'A2'
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='0F766E')
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(80, max(18, max(len(str(c.value or '')) for c in column) + 3))
        for row in writer.book['KPI Summary'].iter_rows(min_row=2):
            row[1].number_format = '#,##0' if row[2].value == 'count' else '#,##0.00'
        for row in writer.book['Filters'].iter_rows(min_row=2):
            row[0].alignment = Alignment(wrap_text=True, vertical='top')
            writer.book['Filters'].row_dimensions[row[0].row].height = 72 if row[0].row == 2 else 36
    return output.getvalue()


def findings_text(findings, filters, currency):
    content = ('Elevate – Retail Sales Analytics Report\n' + '=' * 55 + '\n'
               + 'Generated UTC: ' + datetime.now(timezone.utc).isoformat() + '\n'
               + filter_description(filters) + f'\nCurrency: {currency}\nSource: MySQL\n\n'
               + '\n\n'.join(f'{i}. {finding}' for i, finding in enumerate(findings, 1))
               + '\n\nRevenue = Quantity × Unit Price × (1 − Discount)\n'
               + 'Profit = Revenue − Quantity × Cost Price\n'
               + 'Profit Margin = Total Profit ÷ Total Revenue × 100 (N/A for zero revenue)\n')
    return content.encode('utf-8')
