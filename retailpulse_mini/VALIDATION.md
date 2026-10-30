# Validation results

## Elevate rename and dataset deletion

All 18 automated tests pass. Live isolated MySQL and Streamlit checks verified that an unconfirmed delete does nothing, a confirmed delete removes only the selected dataset, other dataset rows remain intact, deleted files can be re-uploaded, and deleting the last dataset shows the empty state. Unit tests verify rollback on failure and bound dataset IDs. No user datasets were deleted during testing. DELETE grants apply only to the app account's datasets and dataset_rows tables; the chatbot remains SELECT-only. The browser title, Home, sidebar, chatbot and retail report branding now use Elevate. Existing folder and database identifiers are retained.

## Flexible dataset upgrade (September 14)

All 15 automated tests pass. The new workflow was additionally tested on an isolated MySQL 8.0.44 server with the user's INDIA_RETAIL_DATA.xlsx: **2,534 accepted rows, zero rejected rows, Sales 2,515,308.50, Profit 285,268.08512232**. Negative profits remain intact. MySQL aggregates match Pandas, and a live Groq call generated and executed a valid query for total Sales.

Additional live checks cover separate HR and text-only datasets, leading-zero IDs, NULL preservation, dataset-ID isolation, duplicate import prevention, parameter ordering with monthly date-format filters, all five Streamlit pages, chart rendering, and filter persistence between dashboard and reports. The generic migration is additive. The user's main MySQL database must run `database/generic_schema.sql` before the new storage is available; the development tests do not install tables into the user's database.

The older validation record below applies to the preserved original retail workflow. Live Groq calls have now also been verified for the flexible workflow using openai/gpt-oss-120b.

Validated locally on Windows with Python 3.12.14 and an isolated MySQL 8.0.44 instance. The existing MySQL service and databases were not modified.

## Passed

- All eight unittest tests, including parametrized cleaning and SQL attack cases.
- `streamlit run app.py` starts successfully (with a temporary port override for this check); the HTTP health endpoint returns `ok`. `pip check` reports no broken requirements.
- All 5,000 sample lines pass validation and import into the normalized MySQL schema.
- Live MySQL totals match Pandas calculations: revenue **INR 24,348,069.40**, profit **INR 7,802,019.40**, **2,500 orders**, **591 customers**, AOV **INR 9,739.23**, profit margin **32.04%**.
- Date/category/region filters return the expected sales subset.
- Monthly chatbot SQL returns 24 months; result limits cap returned rows at 200.
- A malicious-looking bound filter value remains a literal string.
- Repeated files, overlapping order lines, and conflicting customer metadata roll back without extra records or upload logs.
- The dedicated reader account cannot read the customers table or delete order items.
- All five pages run using Streamlit AppTest against the populated temporary database, with six KPI cards, rendered dashboard charts, and filter persistence between dashboard and reports.
- Missing Groq credentials produce a user-visible configuration message without a page exception.
- The real LangChain prompt/runnable pipeline is exercised with a mocked ChatGroq response, including malformed JSON handling.
- CSV contents, Excel workbook values/sheets, text report source context, zero-revenue margin handling, and spreadsheet formula escaping are tested.

## Not tested live

Groq provider calls require your API key. Natural-language SQL accuracy, provider availability, quotas, and actual model response latency were not tested. The tests establish query validation and execution behavior, not universal correctness of model-generated SQL. UI checks use Streamlit's runtime testing framework, not a browser screenshot review.

## Library versions used

Streamlit 1.63.0; mysql-connector-python 9.7.0; Pandas 3.0.1; NumPy 2.3.5; Matplotlib 3.11.2; Seaborn 0.13.2; LangChain 1.4.0; langchain-groq 1.1.3; Python-dotenv 1.2.3; OpenPyXL 3.1.5.

The requirements file permits compatible version ranges. Re-run the included tests after upgrading dependencies.
