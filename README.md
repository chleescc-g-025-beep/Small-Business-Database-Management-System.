# Small Business Database Management System

## Project Overview

The Small Business Database Management System is a beginner-friendly data engineering project designed to demonstrate how raw business data can be cleaned, validated, stored, and transformed into useful business reports.

The project uses Python, Pandas, SQLite, and SQL to process customer information, product inventory, and sales transactions.

It includes an ETL pipeline, data quality checks, rejected-record tracking, relational database storage, SQL reporting, and automated tests.

## Objectives

- Build a relational database for a small business.
- Import business data from CSV files.
- Clean and validate incoming data.
- Identify and record invalid sales records.
- Load validated data into SQLite.
- Generate reports using SQL.
- Test database integrity and business calculations.
- Demonstrate safe pipeline reruns without duplicating existing orders.

## Technologies Used

- Python 3.12
- Pandas
- SQLite
- SQL
- pytest
- Git and GitHub

## Project Structure

```text
small-business-database/
├── data/
│   ├── raw/
│   │   ├── customers.csv
│   │   ├── products.csv
│   │   └── sales.csv
│   └── processed/
├── database/
│   ├── schema.sql
│   └── small_business.db
├── scripts/
│   ├── create_database.py
│   └── run_pipeline.py
├── sql/
│   └── reports.sql
├── tests/
│   └── test_database.py
├── requirements.txt
├── .gitignore
└── README.md
```

## Database Design

The database contains four main tables.

### Customers

Stores customer details, including names, email addresses, and telephone numbers.

### Products

Stores product names, categories, prices, and available stock quantities.

### Orders

Stores order references, customer relationships, order dates, and order statuses.

### Order Items

Stores the products and quantities associated with each order, together with the unit prices used for those sales.

Primary keys, foreign keys, unique constraints, and validation rules help maintain data integrity.

## ETL Pipeline

The pipeline follows three main stages.

### 1. Extract

Reads customer, product, and sales data from CSV files using Pandas.

### 2. Transform

Cleans and validates the incoming data. Examples include:

- Normalising email addresses.
- Validating customer and product references.
- Checking order dates and statuses.
- Rejecting zero or negative sales quantities.
- Detecting duplicate sales lines.
- Identifying inconsistent order information.

Invalid records are recorded in a rejected-records report.

### 3. Load

Loads validated customer, product, order, and order-item data into SQLite.

The pipeline also checks for existing orders so that rerunning it does not insert the same order references again.

## SQL Reports

The project includes SQL queries for:

1. Overall business performance.
2. Revenue by product.
3. Daily sales revenue.
4. Customer spending.
5. Current inventory.
6. Products requiring restocking.

These reports demonstrate how structured business data can be used to support operational decisions.

## Sample Results

The sample dataset produced the following results:

| Metric | Result |
|---|---:|
| Customers loaded | 5 |
| Products loaded | 6 |
| Orders loaded | 6 |
| Order items loaded | 11 |
| Valid sales rows | 11 |
| Rejected sales rows | 1 |
| Units sold | 21 |
| Total completed sales revenue | 962.49 |

The revenue is expressed in the same currency units as the source data.

### Example Business Insights

- Rice 5kg generated 380.00 in revenue.
- Bread had the highest number of units sold, with 5.
- Simphiwe Leeuw had the highest total customer spending, at 350.50.
- Laundry Detergent had 20 units remaining in stock.

## Installation and Setup

### Prerequisites

Install Python 3 and SQLite. A Python virtual environment is recommended.

On Ubuntu, SQLite can be installed using:

```bash
sudo apt update
sudo apt install sqlite3
```

### 1. Clone the Repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd small-business-database
```

Replace `<YOUR_REPOSITORY_URL>` with the actual GitHub repository URL.

### 2. Create and Activate a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the Database

```bash
python scripts/create_database.py
```

### 5. Run the ETL Pipeline

```bash
python scripts/run_pipeline.py
```

The pipeline processes the CSV files, loads valid records, and generates processing reports.

### 6. Run
