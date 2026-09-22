"""Order Store: the system of record for orders, with in-memory and PostgreSQL implementations."""

from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol, TypedDict, cast

import psycopg
from psycopg.types.json import Jsonb

OrderStatus = Literal["pending", "shipped", "delivered", "cancelled", "refunded"]

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


class ShippingAddress(TypedDict):
    """The exact address shape the evaluation set uses; modify_order arguments must match it."""

    name: str
    street1: str
    street2: str
    city: str
    state: str
    zip: str
    country: str


@dataclass(frozen=True)
class Order:
    order_id: str
    customer_id: str
    total: float
    status: OrderStatus
    shipping_address: ShippingAddress | None = None


class OrderStore(Protocol):
    def get(self, order_id: str) -> Order | None: ...

    def upsert(self, order: Order) -> None: ...

    def set_status(self, order_id: str, status: OrderStatus) -> None:
        """Raises KeyError when the order does not exist."""
        ...

    def set_shipping_address(self, order_id: str, address: ShippingAddress) -> None:
        """Raises KeyError when the order does not exist."""
        ...

    def list(self) -> list[Order]:
        """Every order, sorted by order id."""
        ...


class InMemoryOrderStore:
    def __init__(self) -> None:
        self._orders: dict[str, Order] = {}

    def get(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)

    def upsert(self, order: Order) -> None:
        self._orders[order.order_id] = order

    def set_status(self, order_id: str, status: OrderStatus) -> None:
        self._orders[order_id] = replace(self._orders[order_id], status=status)

    def set_shipping_address(self, order_id: str, address: ShippingAddress) -> None:
        self._orders[order_id] = replace(self._orders[order_id], shipping_address=address)

    def list(self) -> list[Order]:
        return sorted(self._orders.values(), key=lambda order: order.order_id)


class PostgresOrderStore:
    """One `orders` table over a single autocommit connection. Applies the schema on startup."""

    def __init__(self, conninfo: str) -> None:
        self._conn = psycopg.connect(conninfo, autocommit=True)
        self._conn.execute(SCHEMA_FILE.read_bytes())

    def close(self) -> None:
        self._conn.close()

    def get(self, order_id: str) -> Order | None:
        row = self._conn.execute(
            "SELECT order_id, customer_id, total, status, shipping_address"
            " FROM orders WHERE order_id = %s",
            (order_id,),
        ).fetchone()
        return _order_from_row(row) if row else None

    def upsert(self, order: Order) -> None:
        self._conn.execute(
            "INSERT INTO orders (order_id, customer_id, total, status, shipping_address)"
            " VALUES (%s, %s, %s, %s, %s)"
            " ON CONFLICT (order_id) DO UPDATE SET"
            " customer_id = EXCLUDED.customer_id, total = EXCLUDED.total,"
            " status = EXCLUDED.status, shipping_address = EXCLUDED.shipping_address",
            (
                order.order_id,
                order.customer_id,
                order.total,
                order.status,
                Jsonb(order.shipping_address) if order.shipping_address is not None else None,
            ),
        )

    def set_status(self, order_id: str, status: OrderStatus) -> None:
        cursor = self._conn.execute(
            "UPDATE orders SET status = %s WHERE order_id = %s", (status, order_id)
        )
        if cursor.rowcount == 0:
            raise KeyError(order_id)

    def set_shipping_address(self, order_id: str, address: ShippingAddress) -> None:
        cursor = self._conn.execute(
            "UPDATE orders SET shipping_address = %s WHERE order_id = %s",
            (Jsonb(address), order_id),
        )
        if cursor.rowcount == 0:
            raise KeyError(order_id)

    def list(self) -> list[Order]:
        rows = self._conn.execute(
            "SELECT order_id, customer_id, total, status, shipping_address"
            " FROM orders ORDER BY order_id"
        ).fetchall()
        return [_order_from_row(row) for row in rows]


def _order_from_row(row: tuple[object, ...]) -> Order:
    order_id, customer_id, total, status, address = row
    return Order(
        order_id=cast(str, order_id),
        customer_id=cast(str, customer_id),
        total=float(cast(Decimal, total)),
        status=cast(OrderStatus, status),
        shipping_address=cast(ShippingAddress | None, address),
    )
