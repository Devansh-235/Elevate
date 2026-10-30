# Elevate – Flexible Data Analytics Assistant

**Updated: flexible datasets are now the default.** CSV/Excel tables from any domain no longer need the fixed retail columns. Read [GENERIC_DATA_GUIDE.md](GENERIC_DATA_GUIDE.md) and run `database/generic_schema.sql` once in Workbench. The original retail functionality documented below remains available through **Workflow → Original retail**.

A small full-stack retail analytics project: Streamlit is the interface, Python services handle validation and analysis, and MySQL stores normalized sales data. LangChain and ChatGroq translate business questions into restricted SELECT queries. No Flask, FastAPI, React, SQLAlchemy, PostgreSQL, Docker, or cloud database is used.

## What is included

Exactly five pages: **Home**, **Upload Data**, **Sales Dashboard**, **Ask Data Chatbot**, and **Download Report**. The project includes 5,000 fictional sales lines, all source code, SQL schema, a reproducible sample generator, and standard-library unittest tests.

```text
retailpulse_mini/
├── app.py
├── requirements.txt
├── .env.example
├── .gitignore
├── .streamlit/config.toml
├── README.md
├── VALIDATION.md
├── pages/
│   ├── upload.py
│   ├── dashboard.py
│   ├── chatbot.py
│   └── reports.py
├── database/
│   ├── __init__.py
│   ├── connection.py
│   ├── schema.sql
│   └── queries.py
├── services/
│   ├── __init__.py
│   ├── data_cleaning.py
│   ├── analytics.py
│   ├── chatbot_service.py
│   ├── report_generator.py
│   └── ui.py
├── sample_data/
│   ├── retail_sales.csv
│   └── generate_sample.py
├── assets/
│   └── style.css
└── tests/
    └── test_project.py
```

## Windows and VS Code setup

### 1. Install the local tools

Install Python 3.11–3.13, MySQL Community Server **8.0.16 or later**, MySQL Workbench, and VS Code with its Python extension. MySQL Workbench is a client; you also need the MySQL Server service running. Remember the administrator password chosen during installation.

Open the `retailpulse_mini` folder in VS Code. Use **Terminal → New Terminal** (PowerShell) and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the executable directly; no execution-policy change is necessary:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

In VS Code, choose **Python: Select Interpreter** and select `.venv\Scripts\python.exe`.

### 2. Create the database in MySQL Workbench

Connect to your local server as the administrator. Open `database/schema.sql`, run the schema statements using the lightning-bolt action, then refresh the Schemas panel. The database is `retailpulse_mini`.

Create two application accounts by running the following in a new SQL tab. **Replace both example passwords before executing.** These are new application credentials, not your existing administrator password.

```sql
CREATE USER 'retailpulse_app'@'127.0.0.1' IDENTIFIED BY 'YOUR_STRONG_APP_PASSWORD';
GRANT SELECT, INSERT ON retailpulse_mini.* TO 'retailpulse_app'@'127.0.0.1';
GRANT UPDATE ON retailpulse_mini.customers TO 'retailpulse_app'@'127.0.0.1';
GRANT UPDATE ON retailpulse_mini.products TO 'retailpulse_app'@'127.0.0.1';
GRANT UPDATE ON retailpulse_mini.orders TO 'retailpulse_app'@'127.0.0.1';

CREATE USER 'retailpulse_reader'@'127.0.0.1' IDENTIFIED BY 'YOUR_STRONG_READER_PASSWORD';
GRANT SELECT ON retailpulse_mini.retail_sales TO 'retailpulse_reader'@'127.0.0.1';
```

The app account's UPDATE grants are used only for no-op upserts that lock existing dimension rows before checking for conflicts. The importer never changes their existing values. The reader can SELECT only the analytics view, not customers, chat logs, or uploads. The view uses its schema creator's privileges (`SQL SECURITY DEFINER`), so keep that creator account available. Do not use root as either application account. If these named users already exist, inspect their grants in Workbench before changing them.

### 3. Configure `.env`

```powershell
Copy-Item .env.example .env
```

Edit `.env` in VS Code. Enter the two passwords created above, your local host and port, and your Groq API key. Quote passwords containing `#` or spaces. Keep `.env` private; it is excluded by `.gitignore`. No credentials are committed.

```dotenv
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=retailpulse_mini
MYSQL_USER=retailpulse_app
MYSQL_PASSWORD="your actual app password"
MYSQL_READONLY_USER=retailpulse_reader
MYSQL_READONLY_PASSWORD="your actual reader password"
GROQ_API_KEY="your actual Groq API key"
GROQ_MODEL=llama-3.3-70b-versatile
CURRENCY_SYMBOL=INR
```

Obtain an API key from the [Groq console](https://console.groq.com/keys). Model availability can change: select an available ChatGroq-compatible model in `GROQ_MODEL` if the default is unavailable. Uploads, dashboard, and reports work without a Groq key. Restart Streamlit after editing `.env`.

### 4. Run the application

From the project folder, with the environment activated:

```powershell
streamlit run app.py
```

Without activation:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the local URL printed by Streamlit, normally `http://localhost:8501`. Upload `sample_data/retail_sales.csv`, select ISO date format, review the 5,000 valid rows, and click **Insert cleaned records into MySQL**. Explore the dashboard, ask a question, and download the three report formats.

## Data contract and cleaning

Required headers (case-sensitive, surrounding whitespace trimmed):

```text
Order ID, Order Date, Customer ID, Customer Name, Product ID, Product Name,
Category, Quantity, Unit Price, Cost Price, Discount, City, Region
```

- CSV must be UTF-8; Excel must be `.xlsx` (first worksheet). Legacy `.xls` is not supported by OpenPyXL. Limits: 20 MB and 100,000 records per file. Extra columns are ignored.
- Identifiers are strings, preserving leading zeroes in CSV. In Excel, store IDs as text to preserve leading zeroes. All required cells must be present.
- Quantity must be an integer from 1 to 1,000,000. Unit Price and Cost Price must be finite, nonnegative, at most 9,999,999,999.99, with at most two decimal places.
- Discount is a **fraction**, 0 through 1, with at most five decimal places. `0.10` means 10%; `10` is rejected. Free items and 100% discounts are valid. Negative profit is valid and retained.
- Choose ISO, day-first, or month-first dates explicitly. Real Excel date cells are supported. Impossible dates are rejected; time-of-day inputs are not supported. Dates must fit Pandas' timestamp range.
- Text is trimmed and length-checked. Dates and numerics are normalized. Exact duplicate valid records keep their first occurrence; later copies are rejected. If different rows have the same Order ID + Product ID, all conflicting rows are rejected. Combine repeated product lines into one line before uploading.
- A Customer ID must map to one name; a Product ID to one product name/category; an Order ID to one date/customer/city/region. Conflicting rows within a file are rejected. Prices and costs are stored per order item and may change between orders.
- The preview shows total, valid, invalid, duplicate, and missing-cell counts. Rejected exports retain original values, source row numbers (header is row 1), and reasons. Formula-like text is prefixed with an apostrophe in spreadsheet exports for safe opening.
- Inserts are atomic. The file hash prevents importing the identical file twice; the order/product unique key prevents duplicate lines from renamed or overlapping files. A conflict with existing MySQL records rolls back the **entire import** with an error. Such database conflicts do not change the file-validation counts; correct/remove existing or conflicting rows and retry. No silent overwrite or partial import occurs.

## Storage and calculations

`customers` → `orders` → `order_items` ← `products`; `uploaded_files` tracks the source of each item. `chat_history` stores successful questions, SQL, bound parameters, and the rendered answer. All six tables use primary keys; sales relationships use foreign keys; quantities, prices, discounts, and upload counts have database constraints. `retail_sales` is an additional **view**, not a seventh table.

MySQL computes Revenue and Profit as generated decimal columns:

```text
Revenue = Quantity × Unit Price × (1 − Discount)
Profit = Revenue − Quantity × Cost Price
Profit Margin = Total Profit ÷ Total Revenue × 100
Average Order Value = Total Revenue ÷ COUNT(DISTINCT Order ID)
```

The dashboard and report pages query the MySQL view with parameterized date, category, city, and region filters. Pandas aggregates the retrieved rows. No uploaded preview or sample CSV is used as a dashboard fallback. Currency is a display label, not a conversion; use one currency throughout the database. Revenue/profit retain database precision, then use floating-point Pandas analysis and two-decimal display rounding. This is an analytics demo, not a financial ledger.

The six KPIs are revenue, profit, distinct orders, distinct customers, average order value, and weighted overall profit margin. Margin is N/A at zero revenue. Product/category filtering can select only some lines of an order; AOV therefore means filtered revenue per distinct filtered order. Empty selections mean all; multiple filter types are combined with AND. Dashboard and report filters persist across page switches within the session.

Charts show monthly sales, category revenue, top five products by revenue, region revenue, and monthly revenue versus profit. Monthly series include zero-sales gaps between the first and last matching months.

Findings define best-selling as highest units, most profitable category as highest total profit, weakest region as lowest total revenue, and high-sales/low-profit as top revenue quartile with below-overall profit margin. Ties are resolved deterministically. Discount bands show aggregate profit margins; the report also calculates the arithmetic profit reduction versus the same units at list price. This comparison does not prove discounts caused changes in demand.

## Ask Elevate

LangChain's `ChatPromptTemplate` and `ChatGroq` request structured JSON containing a query and parameter array. There is no general-purpose SQL agent and no SQLAlchemy dependency.

1. The model receives the schema, current question, and five recent successful questions/SQL.
2. A fail-closed tokenizer allows one SELECT against `retail_sales`, known columns, and a short function allowlist. No joins, CTEs, subqueries, database prefixes, comments, variables, raw string literals, or multiple statements are accepted. All filtering strings use `%s` placeholders. Destructive SQL including INSERT, UPDATE, DELETE, DROP, ALTER, CREATE and TRUNCATE is blocked.
3. SQL is validated again at execution. A separate view-only account executes it inside a read-only transaction. Queries have a 3-second server SELECT timeout and a 200-row result cap. LIMIT numbers are explicitly validated, not user-string interpolated. A blocked/malformed query produces an error and is never executed.
4. Retrieved rows are shown in a table with expandable SQL/parameters. A simple business answer formats the first five returned rows directly, avoiding a second model call that could invent numbers. SQL result aliases explain the measures. Review SQL for interpretation: SELECT-only validation prevents unsafe operations but cannot guarantee that the model understood a business question correctly.
5. Ten recent successful turns are kept in Streamlit session state, with five sent as context. Clear recent conversation resets session context; it does not delete the MySQL audit log. Failed questions are not persisted.

Chatbot questions apply to all stored data unless the question specifies filters. The dashboard's filters are not implicitly applied. Questions and their recent SQL go to Groq; result tables are not sent back for summarization. Do not put secrets in questions. Follow-up questions always trigger a fresh database query.

Example questions:

- What is the total revenue?
- Which five products generated the highest profit?
- Show monthly sales trends.
- Which category is underperforming?
- Compare sales across different regions.
- Which month generated the highest revenue?
- What was the profit margin in North during 2025?

## Downloads

Filtered sales CSV contains the exact filtered rows and MySQL-derived revenue/profit. KPI Excel contains a styled summary and filter context. The UTF-8 text report contains the findings, definitions, selected filters, currency, source, and timestamp. All files are generated in memory from the current database snapshot.

## Tests and troubleshooting

```powershell
python -m unittest discover -s tests -v
python -m compileall -q app.py database services pages
```

Tests require the project dependencies, but do not need MySQL or a Groq key. They cover the full sample, invalid numeric values, missing fields, duplicate/conflicting records, date parsing, Excel imports, SQL attacks rejected before connection, KPI arithmetic, zero revenue, and export contents.

See [VALIDATION.md](VALIDATION.md) for the completed live MySQL and Streamlit checks, exact tested library versions, and the limitation that live Groq calls require your own key.

For a live check in Workbench after importing the sample:

```sql
USE retailpulse_mini;
SELECT COUNT(*) AS lines, COUNT(DISTINCT order_id) AS orders,
       SUM(revenue) AS revenue, SUM(profit) AS profit FROM retail_sales;
-- Expected: 5,000 lines; 2,500 orders; revenue 24348069.4; profit 7802019.4.
SELECT * FROM uploaded_files ORDER BY upload_id DESC;
SHOW GRANTS FOR 'retailpulse_reader'@'127.0.0.1';
```

- **Access denied / connection failed:** check `.env`, the running MySQL service, port, user host, and Workbench grants. Restart Streamlit after changes. The app intentionally hides raw driver errors that might reveal configuration details; it shows the MySQL error number.
- **Table/view missing:** run the schema as an administrator first. `schema.sql` creates fresh tables and is not a migration tool for older incompatible schemas.
- **Already imported:** use new Order IDs for new sales. Remove previously stored order/product pairs from overlapping files; changing the filename does not bypass duplicate protection.
- **Chatbot unavailable:** set both reader credentials and the Groq key. Check the selected model and quota. Try a simpler question if SQL is outside the supported dialect. Invalid SQL or a timed-out query is not retried automatically against the database.
- **Port 8501 busy:** use `streamlit run app.py --server.port 8502`.
- **No matching sales:** clear filters or upload data. The application never displays invented demo KPIs.

This is a local, single-team learning application without login, tenant isolation, inventory, tax, returns, or exchange rates. Keep it local. Streamlit and LangChain install their own transitive dependencies; application code uses only the requested libraries and Python standard library.

## API references

The navigation uses the official [Streamlit Page/navigation API](https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation). The chatbot uses the official [LangChain ChatGroq integration](https://reference.langchain.com/python/langchain-groq/chat_models/ChatGroq). Read-only transactions use [MySQL Connector/Python start_transaction](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlconnection-start-transaction.html).
