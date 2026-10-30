"""Domain-neutral analysis: labels and units come from the actual dataset."""
import pandas as pd


def summarize(frame, columns, metric=None, category=None, date_column=None, aggregation='Sum'):
    labels = {c['sql_name']: c['name'] for c in columns}
    nums = [c['sql_name'] for c in columns if c['kind'] == 'Number']
    numeric = frame[nums].describe().T if nums and not frame.empty else pd.DataFrame()
    if not numeric.empty:
        numeric.index = [labels[c] for c in numeric.index]
        numeric = numeric.reset_index(names='Column')
    quality = pd.DataFrame([{'Column': c['name'], 'Type': c['kind'],
                             'Missing': int(frame[c['sql_name']].isna().sum()),
                             'Distinct': int(frame[c['sql_name']].nunique())} for c in columns])
    kpis = {'Rows': len(frame), 'Columns': len(columns), 'Missing cells': int(frame.isna().sum().sum())}
    operation = {'Sum': 'sum', 'Mean': 'mean', 'Median': 'median', 'Minimum': 'min', 'Maximum': 'max'}[aggregation]
    def reduce(group):
        return group.sum(min_count=1) if operation == 'sum' else getattr(group, operation)()
    if metric:
        values = frame[metric]
        kpis[f'{aggregation} of {labels[metric]}'] = reduce(values)
        kpis[f'Mean of {labels[metric]}'] = values.mean()
        kpis[f'Nonmissing {labels[metric]}'] = int(values.notna().sum())
    groups, trend = pd.DataFrame(), pd.DataFrame()
    if category:
        if metric:
            groups = reduce(frame.groupby(category, dropna=False)[metric]).reset_index(name='Value')
        else:
            groups = frame.groupby(category, dropna=False).size().reset_index(name='Value')
        groups = groups.sort_values('Value', ascending=False, na_position='last')
    if date_column:
        dated = frame.dropna(subset=[date_column]).copy()
        dated['Period'] = dated[date_column].dt.to_period('M').dt.to_timestamp()
        if not dated.empty:
            trend = (reduce(dated.groupby('Period')[metric]).reset_index(name='Value') if metric else
                     dated.groupby('Period').size().reset_index(name='Value'))
    findings = [f'{len(frame):,} rows match the current filters. There are {int(frame.isna().sum().sum()):,} missing cells.']
    if metric:
        value = kpis[f'{aggregation} of {labels[metric]}']
        findings.append(f'{aggregation} of {labels[metric]}: {value:,.4f}.' if pd.notna(value) else
                        f'{labels[metric]} has no nonmissing values in this selection.')
    if not groups.empty and groups['Value'].notna().any():
        high, low = groups.dropna(subset=['Value']).iloc[[0, -1]].to_dict('records')
        measure = f'{aggregation.lower()} of {labels[metric]}' if metric else 'row count'
        findings.append(f'Highest {measure} by {labels[category]}: {high[category]} ({high["Value"]:,.4f}); '
                        f'lowest: {low[category]} ({low["Value"]:,.4f}). Highest/lowest does not imply better/worse performance.')
    if not trend.empty and trend['Value'].notna().any():
        peak = trend.loc[trend.Value.idxmax()]
        findings.append(f'Highest observed monthly value: {peak.Period:%B %Y}, {peak.Value:,.4f}. '
                        'Months with no records are not assumed to be zero.')
    findings.append('Only supplied fields are analysed. No revenue, profit, identifier, unit, or causal explanation is inferred.')
    return {'kpis': kpis, 'numeric': numeric, 'quality': quality, 'groups': groups, 'trend': trend, 'findings': findings}
