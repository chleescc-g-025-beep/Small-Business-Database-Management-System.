import shutil
import sqlite3
import scripts.run_pipeline as pipeline
import pandas as pd

from scripts.run_pipeline import (
    clean_customers,
    clean_products,
    clean_sales,
)


def test_customer_emails_are_normalised():
    """Emails should be trimmed and converted to lowercase."""
    customers = pd.DataFrame(
        {
            "first_name": [" Simphiwe "],
            "last_name": [" Leeuw "],
            "email": [" SIMPHIWE@EXAMPLE.COM "],
        }
    )

    cleaned, rejected = clean_customers(customers)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["first_name"] == "Simphiwe"
    assert cleaned.iloc[0]["last_name"] == "Leeuw"
    assert cleaned.iloc[0]["email"] == "simphiwe@example.com"
    assert rejected.empty


def test_invalid_customer_email_is_rejected():
    """Customers with invalid email addresses should be rejected."""
    customers = pd.DataFrame(
        {
            "first_name": ["Thando"],
            "last_name": ["Mbeki"],
            "email": ["invalid-email"],
        }
    )

    cleaned, rejected = clean_customers(customers)

    assert cleaned.empty
    assert len(rejected) == 1
    assert rejected.iloc[0]["rejection_reason"] == (
        "Missing required field or invalid email"
    )


def test_invalid_product_price_is_rejected():
    """Products with negative prices should be rejected."""
    products = pd.DataFrame(
        {
            "product_name": ["Rice 5kg"],
            "category": ["Groceries"],
            "price": [-10.00],
            "stock_quantity": [20],
        }
    )

    cleaned, rejected = clean_products(products)

    assert cleaned.empty
    assert len(rejected) == 1


def test_zero_quantity_sale_is_rejected():
    """Sales with zero quantities should not enter the cleaned dataset."""
    customers = pd.DataFrame(
        {
            "email": ["simphiwe@example.com"],
        }
    )

    products = pd.DataFrame(
        {
            "product_name": ["Rice 5kg"],
        }
    )

    sales = pd.DataFrame(
        {
            "order_ref": ["ORD001"],
            "customer_email": [" SIMPHIWE@EXAMPLE.COM "],
            "order_date": ["2026-10-20"],
            "status": ["COMPLETED"],
            "product_name": ["Rice 5kg"],
            "quantity": [0],
            "unit_price": [95.00],
        }
    )

    cleaned, rejected = clean_sales(sales, customers, products)

    assert cleaned.empty
    assert len(rejected) == 1
    assert rejected.iloc[0]["rejection_reason"] == (
        "Invalid field or unknown customer/product"
    )


def test_sales_email_is_normalised():
    """Sales emails should match normalised customer emails."""
    customers = pd.DataFrame(
        {
            "email": ["simphiwe@example.com"],
        }
    )

    products = pd.DataFrame(
        {
            "product_name": ["Rice 5kg"],
        }
    )

    sales = pd.DataFrame(
        {
            "order_ref": ["ORD001"],
            "customer_email": [" SIMPHIWE@EXAMPLE.COM "],
            "order_date": ["2026-10-20"],
            "status": ["COMPLETED"],
            "product_name": ["Rice 5kg"],
            "quantity": [2],
            "unit_price": [95.00],
        }
    )

    cleaned, rejected = clean_sales(sales, customers, products)

    assert len(cleaned) == 1
    assert cleaned.iloc[0]["customer_email"] == "simphiwe@example.com"
    assert cleaned.iloc[0]["quantity"] == 2
    assert rejected.empty

def test_pipeline_does_not_duplicate_existing_orders(tmp_path, monkeypatch):
    """Loading the same order twice must not create duplicates."""

    # Use a temporary database instead of the real project database.
    test_database = tmp_path / "test_database.db"
    monkeypatch.setattr(pipeline, "DATABASE_FILE", test_database)

    # Create the database tables using the project's actual schema.
    schema_path = pipeline.PROJECT_DIR / "database" / "schema.sql"

    with sqlite3.connect(test_database) as connection:
        connection.executescript(
            schema_path.read_text(encoding="utf-8")
        )

    # Prepare one customer.
    customers = pd.DataFrame(
        [
            {
                "first_name": "Simphiwe",
                "last_name": "Leeuw",
                "email": "simphiwe@example.com",
                "phone": "0712345678",
            }
        ]
    )

    # Prepare one product.
    products = pd.DataFrame(
        [
            {
                "product_name": "Rice 5kg",
                "category": "Groceries",
                "price": 95.00,
                "stock_quantity": 40,
            }
        ]
    )

    # Prepare one order containing one product.
    sales = pd.DataFrame(
        [
            {
                "order_ref": "TEST001",
                "customer_email": "simphiwe@example.com",
                "order_date": pd.Timestamp("2026-10-20"),
                "status": "COMPLETED",
                "product_name": "Rice 5kg",
                "quantity": 2,
                "unit_price": 95.00,
            }
        ]
    )

    # First run should insert the order.
    first_result = pipeline.load_data(customers, products, sales)

    assert first_result == (1, 0)

    # Second run should skip the existing order.
    second_result = pipeline.load_data(customers, products, sales)

    assert second_result == (0, 1)

    # Confirm that the order and its item exist only once.
    with sqlite3.connect(test_database) as connection:
        order_count = connection.execute(
            "SELECT COUNT(*) FROM orders WHERE order_ref = ?",
            ("TEST001",),
        ).fetchone()[0]

        item_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM order_items
            JOIN orders ON order_items.order_id = orders.order_id
            WHERE orders.order_ref = ?
            """,
            ("TEST001",),
        ).fetchone()[0]

    assert order_count == 1
    assert item_count == 1

def test_full_pipeline_generates_correct_reports(tmp_path, monkeypatch):
    """Test the full pipeline, its reports and repeated execution."""

    # Create isolated directories for this test.
    raw_dir = tmp_path / "raw"
    processed_dir = tmp_path / "processed"
    database_file = tmp_path / "test_database.db"

    raw_dir.mkdir()
    processed_dir.mkdir()

    # Copy the real input CSVs into the temporary test directory.
    for filename in ("customers.csv", "products.csv", "sales.csv"):
        shutil.copy2(
            pipeline.RAW_DIR / filename,
            raw_dir / filename,
        )

    # Redirect the pipeline away from the real database and output folder.
    monkeypatch.setattr(pipeline, "RAW_DIR", raw_dir)
    monkeypatch.setattr(pipeline, "PROCESSED_DIR", processed_dir)
    monkeypatch.setattr(pipeline, "DATABASE_FILE", database_file)

    # Initialise the temporary database using the project schema.
    schema_path = pipeline.PROJECT_DIR / "database" / "schema.sql"

    with sqlite3.connect(database_file) as connection:
        connection.executescript(
            schema_path.read_text(encoding="utf-8")
        )

    # First execution should import the six orders.
    pipeline.main()

    report_path = processed_dir / "pipeline_report.csv"
    rejected_path = processed_dir / "rejected_records.csv"

    assert report_path.exists()
    assert rejected_path.exists()
    assert (processed_dir / "customers_clean.csv").exists()
    assert (processed_dir / "products_clean.csv").exists()
    assert (processed_dir / "sales_clean.csv").exists()

    report = pd.read_csv(report_path)
    metrics = dict(zip(report["metric"], report["value"]))

    assert int(metrics["customers_accepted"]) == 5
    assert int(metrics["products_accepted"]) == 6
    assert int(metrics["sales_rows_read"]) == 12
    assert int(metrics["sales_rows_accepted"]) == 11
    assert int(metrics["sales_rows_rejected"]) == 1
    assert int(metrics["orders_inserted"]) == 6
    assert int(metrics["orders_skipped_as_existing"]) == 0

    # Check that the rejected record is the invalid sales row.
    rejected = pd.read_csv(rejected_path)

    assert len(rejected) == 1
    assert rejected.iloc[0]["dataset"] == "sales"
    assert "Invalid field" in rejected.iloc[0]["rejection_reason"]

    # Run the pipeline again to check idempotency.
    pipeline.main()

    second_report = pd.read_csv(report_path)
    second_metrics = dict(
        zip(second_report["metric"], second_report["value"])
    )

    assert int(second_metrics["orders_inserted"]) == 0
    assert int(second_metrics["orders_skipped_as_existing"]) == 6

    # Verify the database still contains exactly six orders and 11 items.
    with sqlite3.connect(database_file) as connection:
        order_count = connection.execute(
            "SELECT COUNT(*) FROM orders"
        ).fetchone()[0]

        item_count = connection.execute(
            "SELECT COUNT(*) FROM order_items"
        ).fetchone()[0]

    assert order_count == 6
    assert item_count == 11
