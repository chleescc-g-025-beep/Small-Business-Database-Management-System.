import sqlite3
from pathlib import Path


# Find the project directory regardless of the current terminal location.
PROJECT_DIR = Path(__file__).resolve().parent.parent

SCHEMA_FILE = PROJECT_DIR / "database" / "schema.sql"
DATABASE_FILE = PROJECT_DIR / "database" / "small_business.db"


def create_database():
    """Create the SQLite database and its tables."""

    if not SCHEMA_FILE.exists():
        raise FileNotFoundError(
            f"Database schema not found: {SCHEMA_FILE}"
        )

    DATABASE_FILE.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_FILE) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        schema = SCHEMA_FILE.read_text(encoding="utf-8")
        connection.executescript(schema)

    print("Database created successfully!")
    print(f"Database location: {DATABASE_FILE}")


if __name__ == "__main__":
    create_database()
