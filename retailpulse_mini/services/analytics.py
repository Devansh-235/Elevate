"""Pandas analysis of rows retrieved from the MySQL retail_sales view."""
import numpy as np
import pandas as pd


def analyze(data):
    frame = data.copy()
    for col in ['quantity', 'unit_price', 'cost_price', 'discount', 'revenue', 'profit']:
        frame[col] = pd.to_numeric(frame[col], errors='raise').astype(float)
    frame['order_date'] = pd.to_datetime(frame['order_date'])
    revenue, profit = frame['revenue'].sum(), frame['profit'].sum()
    orders, customers = frame['order_id'].nunique(), frame['customer_id'].nunique()
    kpis = {'Total revenue': revenue, 'Total profit': profit, 'Total orders': orders,
            'Total customers': customers, 'Average order value': revenue / orders if orders else 0,
            'Profit margin': profit / revenue * 100 if revenue else None}
    monthly = (frame.set_index('order_date')[['revenue', 'profit']].resample('MS').sum()
               .rename_axis('month').reset_index()) if len(frame) else pd.DataFrame(columns=['month', 'revenue', 'profit'])
    category = frame.groupby('category', as_index=False)[['revenue', 'profit']].sum().sort_values('revenue', ascending=False)
    products = frame.groupby(['product_id', 'product_name'], as_index=False)[['quantity', 'revenue', 'profit']].sum()
    products['profit_margin'] = np.where(products.revenue.ne(0), products.profit / products.revenue * 100, np.nan)
    regions = frame.groupby('region', as_index=False)[['revenue', 'profit']].sum().sort_values('revenue', ascending=False)
    frame['discount_band'] = pd.cut(frame['discount'], [-.001, 0, .1, .2, .3, 1],
                                    labels=['None', '0–10%', '10–20%', '20–30%', '30–100%'])
    discount = frame.groupby('discount_band', observed=True)[['revenue', 'profit']].sum().reset_index()
    discount['profit_margin'] = np.where(discount.revenue.ne(0), discount.profit / discount.revenue * 100, np.nan)
    return {'data': frame.drop(columns='discount_band'), 'kpis': kpis, 'monthly': monthly,
            'category': category, 'products': products, 'regions': regions, 'discount': discount}


def business_findings(result, currency='INR'):
    data, kpis = result['data'], result['kpis']
    if data.empty:
        return ['No sales match the selected filters.']
    products = result['products']
    best = products.sort_values(['quantity', 'product_id'], ascending=[False, True]).iloc[0]
    profitable = result['category'].sort_values(['profit', 'category'], ascending=[False, True]).iloc[0]
    weak = result['regions'].sort_values(['revenue', 'region']).iloc[0]
    peak = result['monthly'].sort_values(['revenue', 'month'], ascending=[False, True]).iloc[0]
    findings = [
        f"Best-selling product by units: {best.product_name} ({best.product_id}), {best.quantity:,.0f} units.",
        f"Most profitable category: {profitable.category}, {currency} {profitable.profit:,.2f} profit.",
        f"Underperforming region by lowest revenue: {weak.region}, {currency} {weak.revenue:,.2f}. "
        'This compares totals, without adjusting for store count or market size.',
        f"Highest-revenue month: {peak['month']:%B %Y}, {currency} {peak.revenue:,.2f}.",
    ]
    threshold = products.revenue.quantile(.75)
    low_margin = products.loc[(products.revenue >= threshold) &
                             (products.profit_margin < (kpis['Profit margin'] if kpis['Profit margin'] is not None else 0))]
    if low_margin.empty:
        findings.append('No products meet the high-sales/low-profit definition: top revenue quartile '
                        'and a profit margin below the overall margin.')
    else:
        labels = [f'{row.product_name} ({row.profit_margin:.2f}% margin)' for row in
                  low_margin.sort_values('revenue', ascending=False).itertuples()]
        findings.append('High-sales/low-profit products (top revenue quartile, below overall margin): ' + ', '.join(labels) + '.')
    discount_amount = (data.quantity * data.unit_price * data.discount).sum()
    findings.append(f'Discounts reduce revenue and profit by {currency} {discount_amount:,.2f} '
                    'versus the same quantities at list price and unchanged costs. '
                    'This arithmetic comparison does not estimate changes in demand or establish causation.')
    for row in result['discount'].itertuples(index=False):
        margin = f'{row.profit_margin:.2f}%' if pd.notna(row.profit_margin) else 'undefined (zero revenue)'
        findings.append(f'Discount band {row.discount_band}: profit margin {margin}; revenue {currency} {row.revenue:,.2f}.')
    findings.append('Ties use alphabetical product/category/region order or the earliest month.')
    return findings
