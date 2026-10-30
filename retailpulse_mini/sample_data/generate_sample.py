"""Rebuild the fictional 5,000-line sample using only the Python standard library."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path


def generate():
    rng = random.Random(42)
    catalog = [
        ('Electronics', 'Wireless Mouse', 899, 520),
        ('Electronics', 'Bluetooth Speaker', 2499, 1600),
        ('Electronics', 'USB-C Hub', 1899, 1100),
        ('Electronics', 'Headphones', 3299, 2400),
        ('Electronics', 'Keyboard', 1499, 950),
        ('Home', 'Desk Lamp', 1299, 700),
        ('Home', 'Storage Basket', 499, 230),
        ('Home', 'Cotton Bedsheet', 1599, 800),
        ('Home', 'Wall Clock', 799, 410),
        ('Home', 'Cushion Set', 999, 530),
        ('Fashion', 'Cotton T-shirt', 599, 280),
        ('Fashion', 'Running Shoes', 2999, 2000),
        ('Fashion', 'Denim Jeans', 1799, 1000),
        ('Fashion', 'Canvas Bag', 699, 310),
        ('Fashion', 'Cap', 399, 140),
        ('Grocery', 'Coffee Pack', 499, 350),
        ('Grocery', 'Tea Selection', 299, 180),
        ('Grocery', 'Olive Oil', 899, 700),
        ('Grocery', 'Breakfast Oats', 249, 160),
        ('Grocery', 'Almond Pack', 599, 460),
    ]
    places = [('Delhi', 'North'), ('Jaipur', 'North'), ('Mumbai', 'West'),
              ('Pune', 'West'), ('Bengaluru', 'South'), ('Chennai', 'South'),
              ('Kolkata', 'East'), ('Bhubaneswar', 'East')]
    fields = ['Order ID', 'Order Date', 'Customer ID', 'Customer Name',
              'Product ID', 'Product Name', 'Category', 'Quantity', 'Unit Price',
              'Cost Price', 'Discount', 'City', 'Region']
    path = Path(__file__).with_name('retail_sales.csv')
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        # 2,500 orders, two distinct products per order, spanning two calendar years.
        for order in range(1, 2501):
            customer = rng.randint(1, 600)
            day = date(2024, 1, 1) + timedelta(days=rng.randrange(731))
            city, region = rng.choices(places, weights=[15, 8, 19, 12, 17, 13, 9, 7])[0]
            for product in rng.sample(range(len(catalog)), 2):
                category, name, price, cost = catalog[product]
                discount = rng.choices([0, .05, .10, .15, .25, .40], [20, 25, 25, 15, 10, 5])[0]
                writer.writerow([f'ORD-{order:05d}', day.isoformat(), f'C-{customer:04d}',
                                 f'Sample Customer {customer:04d}', f'P-{product+1:03d}',
                                 name, category, rng.randint(1, 8), f'{price:.2f}',
                                 f'{cost:.2f}', f'{discount:.2f}', city, region])
    print(f'Created 5,000 sales records: {path}')


if __name__ == '__main__':
    generate()
