"""
Creates and seeds a sample e-commerce SQLite database so the app is
runnable out of the box. Swap DATABASE_URL in config.py to point at
your own database - the rest of the pipeline (schema introspection,
business context, embeddings) works against any SQLAlchemy-supported DB.
"""
import os
import sqlite3
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    customer_id INTEGER PRIMARY KEY,
    full_name   TEXT NOT NULL,
    email       TEXT NOT NULL,
    signup_date TEXT NOT NULL,
    country     TEXT NOT NULL,
    segment     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    unit_price   REAL NOT NULL,
    in_stock     INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id     INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL,
    order_date   TEXT NOT NULL,
    status       TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

CUSTOMERS = [
    (1, "Ava Thompson", "ava.t@example.com", "2023-01-15", "USA", "retail"),
    (2, "Liam Chen", "liam.chen@example.com", "2023-02-20", "Canada", "retail"),
    (3, "Noor Haddad", "noor.h@example.com", "2022-11-02", "UAE", "enterprise"),
    (4, "Priya Sharma", "priya.s@example.com", "2023-05-11", "India", "retail"),
    (5, "Mateus Silva", "mateus.silva@example.com", "2021-09-30", "Brazil", "enterprise"),
    (6, "Emma Dubois", "emma.d@example.com", "2024-01-08", "France", "retail"),
]

PRODUCTS = [
    (1, "Wireless Mouse", "Electronics", 24.99, 150),
    (2, "Mechanical Keyboard", "Electronics", 79.99, 60),
    (3, "Standing Desk", "Furniture", 349.00, 20),
    (4, "Office Chair", "Furniture", 199.50, 35),
    (5, "USB-C Hub", "Electronics", 39.99, 200),
    (6, "Notebook Set", "Stationery", 12.50, 500),
]

ORDERS = [
    (1, 1, "2024-03-01", "completed"),
    (2, 2, "2024-03-03", "completed"),
    (3, 3, "2024-03-05", "pending"),
    (4, 1, "2024-04-10", "completed"),
    (5, 4, "2024-04-15", "cancelled"),
    (6, 5, "2024-05-02", "completed"),
    (7, 6, "2024-05-20", "completed"),
]

ORDER_ITEMS = [
    (1, 1, 1, 2, 24.99),
    (2, 1, 5, 1, 39.99),
    (3, 2, 2, 1, 79.99),
    (4, 3, 3, 1, 349.00),
    (5, 4, 4, 2, 199.50),
    (6, 5, 6, 5, 12.50),
    (7, 6, 3, 1, 349.00),
    (8, 6, 4, 1, 199.50),
    (9, 7, 2, 2, 79.99),
]


def build_database():
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)
    conn = sqlite3.connect(config.DATABASE_PATH)
    cur = conn.cursor()
    cur.executescript(SCHEMA_SQL)
    cur.executemany("INSERT OR IGNORE INTO customers VALUES (?,?,?,?,?,?)", CUSTOMERS)
    cur.executemany("INSERT OR IGNORE INTO products VALUES (?,?,?,?,?)", PRODUCTS)
    cur.executemany("INSERT OR IGNORE INTO orders VALUES (?,?,?,?)", ORDERS)
    cur.executemany("INSERT OR IGNORE INTO order_items VALUES (?,?,?,?,?)", ORDER_ITEMS)
    conn.commit()
    conn.close()
    print(f"Sample database ready at {config.DATABASE_PATH}")


if __name__ == "__main__":
    build_database()
