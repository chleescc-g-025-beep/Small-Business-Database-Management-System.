import sqlite3
from pathlib import Path

import pandas as pd


PROJECT_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_DIR / "data" / "raw"
PROCESSED_DIR = PROJECT_DIR / "data" / "processed"
DATABASE_FILE = PROJECT_DIR / "database" / "small_business.db"


def read_csv_files():
    """Extract the raw CSV datasets."""
    return (
        pd.read_csv(RAW_DIR / "customers.csv"),
        pd.read_csv(RAW_DIR / "products.csv"),
        pd.read_csv(RAW_DIR / "sales.csv"),
    )


def clean_customers(df):
    """Clean customer data and identify rejected rows."""
    df = df.copy()

    for column in ("first_name", "last_name", "email"):
        df[column] = df[column].astype("string").str.strip()

    df["email"] = df["email"].str.lower()

    valid = (
        df["first_name"].notna()
        & df["first_name"].ne("")
        & df["last_name"].notna()
        & df["last_name"].ne("")
        & df["email"].str.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", na=False
        )
    )

    rejected = df.loc[~valid].copy()
    rejected["rejection_reason"] = "Missing required field or invalid email"

    cleaned = df.loc[valid].drop_duplicates(
        subset=["email"], keep="first"
    ).copy()

    return cleaned, rejected


def clean_products(df):
    """Validate products, prices and stock quantities."""
    df = df.copy()

    for column in ("product_name", "category"):
        df[column] = df[column].astype("string").str.strip()

    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["stock_quantity"] = pd.to_numeric(
        df["stock_quantity"], errors="coerce"
    )

    valid = (
        df["product_name"].notna()
        & df["product_name"].ne("")
        & df["category"].notna()
        & df["category"].ne("")
        & df["price"].notna()
        & df["price"].ge(0)
        & df["stock_quantity"].notna()
        & df["stock_quantity"].ge(0)
        & df["stock_quantity"].mod(1).eq(0)
    )

    rejected = df.loc[~valid].copy()
    rejected["rejection_reason"] = "Invalid product, price or stock"

    valid_df = df.loc[valid].copy()
    duplicates = valid_df.duplicated("product_name", keep="first")

    duplicate_rows = valid_df.loc[duplicates].copy()
    duplicate_rows["rejection_reason"] = "Duplicate product name"

    rejected = pd.concat(
        [rejected, duplicate_rows], ignore_index=True
    )

    cleaned = valid_df.loc[~duplicates].copy()
    cleaned["stock_quantity"] = cleaned["stock_quantity"].astype(int)

    return cleaned, rejected


def clean_sales(df, customers, products):
    """Validate sales rows and reject inconsistent orders."""
    df = df.copy()
    df["_source_row"] = range(2, len(df) + 2)

    for column in ("order_ref", "customer_email", "product_name"):
        df[column] = df[column].astype("string").str.strip()

    df["customer_email"] = df["customer_email"].str.lower()
    df["status"] = df["status"].astype("string").str.strip().str.upper()

    parsed_dates = pd.to_datetime(
        df["order_date"], errors="coerce", format="%Y-%m-%d"
    )
    df["order_date"] = parsed_dates

    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce")

    known_emails = set(customers["email"])
    known_products = set(products["product_name"])

    valid = (
        df["order_ref"].notna()
        & df["order_ref"].ne("")
        & df["customer_email"].isin(known_emails)
        & df["product_name"].isin(known_products)
        & df["order_date"].notna()
        & df["status"].isin(["PENDING", "COMPLETED", "CANCELLED"])
        & df["quantity"].notna()
        & df["quantity"].gt(0)
        & df["quantity"].mod(1).eq(0)
        & df["unit_price"].notna()
        & df["unit_price"].ge(0)
    )

    rejected = df.loc[~valid].copy()
    rejected["rejection_reason"] = "Invalid field or unknown customer/product"

    candidates = df.loc[valid].copy()

    # All rows belonging to an order must agree on customer, date and status.
    inconsistent_refs = set()

    for order_ref, group in candidates.groupby("order_ref"):
        if (
            group["customer_email"].nunique() != 1
            or group["order_date"].nunique() != 1
            or group["status"].nunique() != 1
        ):
            inconsistent_refs.add(order_ref)

    inconsistent = candidates[
        candidates["order_ref"].isin(inconsistent_refs)
    ].copy()

    inconsistent["rejection_reason"] = (
        "Inconsistent customer, date or status within order"
    )

    candidates = candidates[
        ~candidates["order_ref"].isin(inconsistent_refs)
    ].copy()

    rejected = pd.concat(
        [rejected, inconsistent], ignore_index=True
    )

    # Each product may appear only once per order in our schema.
    duplicate_items = candidates.duplicated(
        ["order_ref", "product_name"], keep="first"
    )

    duplicate_rows = candidates.loc[duplicate_items].copy()
    duplicate_rows["rejection_reason"] = (
        "Duplicate product line within order"
    )

    rejected = pd.concat(
        [rejected, duplicate_rows], ignore_index=True
    )

    cleaned = candidates.loc[~duplicate_items].copy()
    cleaned["quantity"] = cleaned["quantity"].astype(int)

    return cleaned, rejected


def load_data(customers, products, sales):
    """Load data transactionally without duplicating existing orders."""
    with sqlite3.connect(DATABASE_FILE) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        # Add customers if they do not already exist.
        for row in customers.itertuples(index=False):
            phone = getattr(row, "phone", None)

            connection.execute(
                """
                INSERT INTO customers
                    (first_name, last_name, email, phone)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO NOTHING
                """,
                (
                    row.first_name,
                    row.last_name,
                    row.email,
                    None if pd.isna(phone) else phone,
                ),
            )

        # Add products if they do not already exist.
        for row in products.itertuples(index=False):
            connection.execute(
                """
                INSERT INTO products
                    (product_name, category, price, stock_quantity)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(product_name) DO NOTHING
                """,
                (
                    row.product_name,
                    row.category,
                    float(row.price),
                    int(row.stock_quantity),
                ),
            )

        customer_ids = dict(
            connection.execute(
                "SELECT email, customer_id FROM customers"
            ).fetchall()
        )

        product_ids = dict(
            connection.execute(
                "SELECT product_name, product_id FROM products"
            ).fetchall()
        )

        inserted_orders = 0
        skipped_orders = 0

        for order_ref, group in sales.groupby("order_ref", sort=False):
            first = group.iloc[0]

            # Skip previously imported orders.
            existing = connection.execute(
                "SELECT 1 FROM orders WHERE order_ref = ?",
                (order_ref,),
            ).fetchone()

            if existing:
                skipped_orders += 1
                continue

            cursor = connection.execute(
                """
                INSERT INTO orders
                    (order_ref, customer_id, order_date, status)
                VALUES (?, ?, ?, ?)
                """,
                (
                    order_ref,
                    customer_ids[first["customer_email"]],
                    first["order_date"].strftime("%Y-%m-%d"),
                    first["status"],
                ),
            )

            order_id = cursor.lastrowid

            for row in group.itertuples(index=False):
                connection.execute(
                    """
                    INSERT INTO order_items
                        (order_id, product_id, quantity, unit_price)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        order_id,
                        product_ids[row.product_name],
                        int(row.quantity),
                        float(row.unit_price),
                    ),
                )

            inserted_orders += 1

    return inserted_orders, skipped_orders


def main():
    """Run extraction, transformation, loading and reporting."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    customers_raw, products_raw, sales_raw = read_csv_files()

    customers, rejected_customers = clean_customers(customers_raw)
    products, rejected_products = clean_products(products_raw)
    sales, rejected_sales = clean_sales(
        sales_raw, customers, products
    )

    customers.to_csv(
        PROCESSED_DIR / "customers_clean.csv", index=False
    )
    products.to_csv(
        PROCESSED_DIR / "products_clean.csv", index=False
    )
    sales.drop(columns=["_source_row"]).to_csv(
        PROCESSED_DIR / "sales_clean.csv", index=False
    )

    rejected_frames = []

    for name, rejected_df in (
        ("customers", rejected_customers),
        ("products", rejected_products),
        ("sales", rejected_sales),
    ):
        if not rejected_df.empty:
            rejected_df = rejected_df.copy()
            rejected_df["dataset"] = name
            rejected_frames.append(rejected_df)

    if rejected_frames:
        all_rejected = pd.concat(
            rejected_frames, ignore_index=True, sort=False
        )
    else:
        all_rejected = pd.DataFrame(
            columns=["dataset", "rejection_reason"]
        )

    all_rejected.to_csv(
        PROCESSED_DIR / "rejected_records.csv", index=False
    )

    inserted_orders, skipped_orders = load_data(
        customers, products, sales
    )

    report = {
        "customers_read": len(customers_raw),
        "customers_accepted": len(customers),
        "customers_rejected": len(rejected_customers),
        "products_read": len(products_raw),
        "products_accepted": len(products),
        "products_rejected": len(rejected_products),
        "sales_rows_read": len(sales_raw),
        "sales_rows_accepted": len(sales),
        "sales_rows_rejected": len(rejected_sales),
        "orders_inserted": inserted_orders,
        "orders_skipped_as_existing": skipped_orders,
    }

    report_df = pd.DataFrame(
        list(report.items()), columns=["metric", "value"]
    )

    report_df.to_csv(
        PROCESSED_DIR / "pipeline_report.csv", index=False
    )

    print("\nETL pipeline completed successfully.")
    print(report_df.to_string(index=False))
    print(f"\nRejected records: {PROCESSED_DIR / 'rejected_records.csv'}")


if __name__ == "__main__":
    main()
