"""Seed the Order Store with the book's scenario orders plus hand-written extras.

Run as ``python -m support_agent.orders.seed`` (``make seed``) against the Postgres in
DATABASE_URL. Seeding upserts, so running it twice leaves the same rows.

Eight scenario pairs (plain cancel and cancel-a-delivered-order) share an order id with
different status and total. Upserting in file order keeps the later, delivered variant.
"""

import json
from pathlib import Path

from support_agent.orders.store import Order, OrderStore, PostgresOrderStore, ShippingAddress
from support_agent.settings import load_settings

SCENARIO_FILE = (
    Path(__file__).parents[1]
    / "eval"
    / "scenarios"
    / "ecommerce_customer_support_evaluation_set.jsonl"
)


def _address(name: str, street1: str, city: str, state: str, zip_code: str) -> ShippingAddress:
    return {
        "name": name,
        "street1": street1,
        "street2": "",
        "city": city,
        "state": state,
        "zip": zip_code,
        "country": "US",
    }


# Statuses the book's scenarios never use, so every rule branch can be exercised by hand.
EXTRA_ORDERS = [
    Order(
        "D10001",
        "CUST_shipped_0",
        59.99,
        "shipped",
        _address("Ada", "1 Ship Ln", "Portland", "OR", "97201"),
    ),
    Order(
        "D10002",
        "CUST_shipped_1",
        210.00,
        "shipped",
        _address("Ben", "2 Ship Ln", "Austin", "TX", "73301"),
    ),
    Order(
        "D20001",
        "CUST_cancelled_0",
        18.50,
        "cancelled",
        _address("Cy", "3 Void St", "Denver", "CO", "80201"),
    ),
    Order(
        "D20002",
        "CUST_cancelled_1",
        99.00,
        "cancelled",
        _address("Dee", "4 Void St", "Boston", "MA", "02101"),
    ),
    Order(
        "D30001",
        "CUST_refunded_0",
        42.75,
        "refunded",
        _address("Eve", "5 Back Rd", "Miami", "FL", "33101"),
    ),
    Order(
        "D30002",
        "CUST_refunded_1",
        150.25,
        "refunded",
        _address("Finn", "6 Back Rd", "Seattle", "WA", "98101"),
    ),
]


def scenario_orders() -> list[Order]:
    """The order of every scenario in the vendored JSONL, in file order."""
    lines = SCENARIO_FILE.read_text().splitlines()
    return [Order(**json.loads(line)["order"]) for line in lines if line.strip()]


def seed(store: OrderStore) -> int:
    """Upsert every scenario order and extra into ``store``; returns the number of orders held."""
    for order in scenario_orders() + EXTRA_ORDERS:
        store.upsert(order)
    return len(store.list())


if __name__ == "__main__":
    database_url = load_settings().database_url
    if not database_url:
        raise SystemExit("DATABASE_URL is not set; see .env.example")
    store = PostgresOrderStore(database_url)
    try:
        print(f"Order Store holds {seed(store)} orders")
    finally:
        store.close()
