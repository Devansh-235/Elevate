import json
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill

from services.report_generator import spreadsheet_safe


def context_text(dataset, filters):
    return (f"Dataset: {dataset['name']} (ID {dataset['dataset_id']})\n"
            + 'Source: MySQL\nGenerated UTC: ' + datetime.now(timezone.utc).isoformat()
            + '\nSelections: ' + json.dumps(filters, default=str, ensure_ascii=False))


def export_summary(dataset, result, filters):
    output = BytesIO()
    tables = {'Summary': pd.DataFrame(result['kpis'].items(), columns=['Metric', 'Value']),
              'Numeric statistics': result['numeric'], 'Data quality': result['quality'],
              'Columns': pd.DataFrame(dataset['columns']),
              'Context': pd.DataFrame({'Context': context_text(dataset, filters).splitlines()})}
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for name, table in tables.items():
            table.map(spreadsheet_safe).to_excel(writer, sheet_name=name, index=False, na_rep='N/A')
        for sheet in writer.book:
            sheet.freeze_panes = 'A2'
            for cell in sheet[1]:
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='0F766E')
            for column in sheet.columns:
                sheet.column_dimensions[column[0].column_letter].width = min(65, max(18, max(len(str(c.value or '')) for c in column)+2))
            for row in sheet.iter_rows(min_row=2):
                for cell in row:
                    if isinstance(cell.value, float):
                        cell.number_format = '#,##0.0000'
            if sheet.title == 'Context':
                for row in sheet:
                    row[0].alignment = Alignment(wrap_text=True, vertical='top')
                    sheet.row_dimensions[row[0].row].height = 75
    return output.getvalue()


def export_findings(dataset, result, filters):
    return (context_text(dataset, filters) + '\n\n' + '\n\n'.join(result['findings'])).encode('utf-8')
