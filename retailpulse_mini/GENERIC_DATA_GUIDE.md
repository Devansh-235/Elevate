# Flexible datasets — upgrade guide

Elevate now accepts flat tables from any domain instead of requiring a fixed retail schema. The same Python/Streamlit/MySQL stack is used. Original retail data and workflows are preserved under **Workflow → Original retail**. The default **Flexible datasets** workflow uses independent, selectable datasets.

## One-time MySQL upgrade

In MySQL Workbench, connect as your administrator/root user and execute the whole `database/generic_schema.sql` script. It creates `datasets` (column metadata/import details) and `dataset_rows` (typed row payloads stored as MySQL JSON), and grants the existing reader account SELECT on the new rows table. It does not delete or alter original retail records. MySQL **8.0.21 or later** is required for JSON_TABLE's SQL NULL behavior.

The standard app account's existing SELECT/INSERT privileges cover the new tables. If you use custom account names or a different database, adapt the USE/GRANT statements to your configured accounts. New installations must first complete the original schema and account setup, then run this migration.

## Upload your own workbook

1. Choose **Flexible datasets → Upload Data**.
2. Upload CSV or `.xlsx`; select the worksheet or CSV delimiter, and the row containing the column headings.
3. Review the original preview and detected column types. No column is mandatory.
4. Change a type to Text to preserve IDs, mixed values, leading zeroes or unsupported date formats. Number accepts negative values. Date supports ISO timestamps/Excel date cells, or the explicitly chosen DD/MM/YYYY or MM/DD/YYYY format. Date-times are timezone-naive; retain timezone-aware values as Text.
5. Choose whether type conversion failures reject their rows or become missing values. Missing cells remain NULL. No imputation or formula assumptions are applied. Empty rows are rejected. Duplicate rows are detected but retained unless you explicitly choose to remove them.
6. Name the dataset, review accepted/rejected counts, and click **Save dataset to MySQL**.

The exact same file, worksheet, header and cleaning choices reuse the existing dataset instead of duplicating it. A different file or different cleaning settings create a separate dataset, not an append into unrelated data. Imports are transactional. Limits: 20 MB/file, 100,000 rows/dataset, 150 columns, 180-character unique nonempty column headings, and 2,048 characters per text cell. Text over that limit is rejected or explicitly converted to missing, never silently truncated. Numbers use double precision for analysis, not financial-ledger precision. Large numeric identifiers should be Text.

## Your INDIA_RETAIL_DATA.xlsx

Choose worksheet **retails**, header row **1**, and ISO/Excel dates. The application discovers its existing fields including **Sales**, **Profit**, **QtyOrdered**, **Product Type**, **Product Sub-Category**, **Region**, **Order Date**, and **Ship Date**. Missing Order ID/Customer ID/Cost Price does not block import. Negative Profit is valid. Sales and Profit are used as supplied; no substitute retail formula is applied.

On Data Dashboard select **Sales** as the measure, **Sum** as the aggregation, **Product Type** or **Region** for comparison, and **Order Date** for monthly trends. Select **Profit** to inspect profitability. You can ask “What is the total Sales?”, “Compare Sales by Region”, or “Show monthly Sales using Order Date”. The app cannot count unique orders or customers without appropriate IDs, and will not invent them.

## Dashboard and reports

Select a saved dataset, a numeric measure (optional), comparison field (optional), date field (optional), and aggregation (Sum, Mean, Median, Minimum, Maximum). No currency or business meaning is assumed. Text-only datasets still provide row counts, distinct counts, missing-value summaries, and category frequencies. Numeric and date charts appear only when their inputs exist.

Filters and analysis choices are shared between dashboard and reports for each dataset. Selecting a date range excludes missing dates; set the date field to None to include those records. An empty category selection means all categories. Missing category values have a selectable Missing entry. Full category results are available in a table; charts show the top ten. Months without observations are not automatically filled with zero. Highest/lowest groups describe magnitudes, not better/worse performance or causation.

Downloads contain filtered original-label CSV data, an Excel summary (KPIs, numeric statistics, quality, schema and filter context), and a text findings report. Formula-like text is escaped for spreadsheet safety.

## Chatbot behavior

Each dataset has separate session conversation history. The prompt receives only its schema and recent questions/SQL, not raw result rows. Generated SQL may query only the logical `dataset` source with its displayed `c_...` SQL column names. The application expands this into a trusted JSON_TABLE projection with a parameter-bound dataset ID. The model cannot choose a different dataset or table. Filtering values remain bound parameters, including those inside SELECT expressions. The existing SELECT validator, function allowlist, 200-row cap, read-only account, read-only transaction, and 3-second SELECT timeout remain in effect.

SQL answers are retrieved from MySQL and formatted directly. A missing or ambiguous measure produces a request to ask about an available field rather than fabricated values. Questions use all rows of the selected dataset unless the question itself specifies filters; dashboard filters are not implicit. A SELECT-only guard does not guarantee perfect interpretation of business terminology—review the SQL and results.

The reader's new grant covers the shared dataset_rows table; application scoping separates datasets within this local app. This is not multi-user tenant isolation or an access-controlled hosted service.

## Delete a dataset

Existing installations: run `database/enable_dataset_deletion.sql` once as root in Workbench. It grants DELETE only on `datasets` and `dataset_rows` to the app account; it does not delete data. Fresh generic installations already include these grants in `generic_schema.sql`. The chatbot reader still has no write permissions.

On Data Dashboard only, select the dataset and expand **Manage dataset · Delete**. Review its name, ID and row count, tick the confirmation, then click **Delete selected dataset**. The dataset entry and all its rows are deleted in one transaction. A failed delete rolls back. Other datasets and original retail tables are not deleted. The deleted dataset's current-session filters and conversation are cleared; historical chat audit logs and previously downloaded reports are retained. The same source file can be uploaded again afterward. There is no undo.

Elevate is the application's display name. Existing project directory and MySQL names remain `retailpulse_mini` so existing installations and credentials continue to work.

## Restart the updated application

Save any open editor buffers carefully so they do not overwrite updated files. Stop Streamlit with Ctrl+C, then run from the folder containing app.py:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Open the exact URL shown in the terminal. If you have multiple project copies or servers, they each have their own `.env` and code; this upgrade is applied to the Codex output project and `C:\Users\asus\OneDrive\Documents\langgraph_tutorials\retailpulse_mini`.
