import sqlite3
from pathlib import Path

import pytest

from scripts.run_pipeline import (
    clean_customers,
    clean_products,
    clean_sales,
    load_data,
    read_csv_files,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT_DIR / "database" / "schema.sql"


@pytest.fixture
def connection(tmp_path, monkeypatch):
    """Create and populate an isolated temporary database."""
    database_path = tmp_path / "test_small_business.db"

    # Redirect the ETL loader to the temporary database.
    monkeypatch.setattr(
        "scripts.run_pipeline.DATABASE_FILE",
        database_path,
    )

    # Create the database tables.
    with sqlite3.connect(database_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(
            SCHEMA_PATH.read_text(encoding="utf-8")
        )

    # Read and clean the sample data.
    customers_raw, products_raw, sales_raw = read_csv_files()
    customers, _ = clean_customers(customers_raw)
    products, _ = clean_products(products_raw)
    sales, _ = clean_sales(sales_raw, customers, products)

    # Load the sample data into the temporary database.
    load_data(customers, products, sales)

    # Open a connection for the tests.
    conn = sqlite3.connect(database_path)
    conn.execute("PRAGMA foreign_keys = ON")

    yield conn

    conn.close()


def test_required_tables_exist(connection):
    """Check that all four required tables exist."""
    cursor = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        """
    )

    tables = {row[0] for row in cursor.fetchall()}

    assert {
        "customers",
        "products",
        "orders",
        "order_items",
    }.issubset(tables)


def test_expected_record_counts(connection):
    """Verify the expected sample data is present."""
    expected_counts = {
        "customers": 5,
        "products": 6,
        "orders": 6,
        "order_items": 11,
    }

    for table, expected_count in expected_counts.items():
        cursor = connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        )
        assert cursor.fetchone()[0] == expected_count


def test_orders_have_valid_customers(connection):
    """Check that every order references an existing customer."""
    cursor = connection.execute(
        """
        SELECT COUNT(*)
        FROM orders AS o
        LEFT JOIN customers AS c
            ON o.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
        """
    )

    assert cursor.fetchone()[0] == 0


def test_order_items_have_valid_products(connection):
    """Check that every order item references an existing product."""
    cursor = connection.execute(
        """
        SELECT COUNT(*)
        FROM order_items AS oi
        LEFT JOIN products AS p
            ON oi.product_id = p.product_id
        WHERE p.product_id IS NULL
        """
    )

    assert cursor.fetchone()[0] == 0


def test_completed_sales_revenue(connection):
    """Verify the expected revenue calculation."""
    cursor = connection.execute(
        """
        SELECT ROUND(SUM(oi.quantity * oi.unit_price), 2)
        FROM orders AS o
        JOIN order_items AS oi
            ON o.order_id = oi.order_id
        WHERE o.status = 'COMPLETED'
        """
    )

    assert cursor.fetchone()[0] == pytest.approx(962.49)


def test_order_references_are_unique(connection):
    """Ensure each order reference occurs only once."""
    cursor = connection.execute(
        """
        SELECT order_ref, COUNT(*)
        FROM orders
        GROUP BY order_ref
        HAVING COUNT(*) > 1
        """
    )

    assert cursor.fetchall() == []


def test_order_items_have_positive_quantities(connection):
    """Ensure no stored order item has an invalid quantity."""
    cursor = connection.execute(
        """
        SELECT COUNT(*)
        FROM order_items
        WHERE quantity <= 0
        """
    )

    assert cursor.fetchone()[0] == 0
