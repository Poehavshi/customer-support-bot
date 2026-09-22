"""Contract tests: both Order Store implementations must behave identically."""

import pytest

from support_agent.orders.store import Order, OrderStore, ShippingAddress

ADDRESS: ShippingAddress = {
    "name": "Customer2",
    "street1": "175 Elm St",
    "street2": "",
    "city": "Metropolis",
    "state": "CA",
    "zip": "95303",
    "country": "US",
}
NEW_ADDRESS: ShippingAddress = {**ADDRESS, "street1": "1 New Rd", "zip": "10001"}

PENDING = Order("B73973", "CUST_cancel_1_cancel", 184.43, "pending", ADDRESS)
DELIVERED = Order("A89268", "CUST_refund_0", 34.32, "delivered")


def test_get_unknown_order_returns_none(store: OrderStore) -> None:
    assert store.get("nope") is None


def test_upsert_then_get_round_trips_every_field(store: OrderStore) -> None:
    store.upsert(PENDING)
    store.upsert(DELIVERED)

    assert store.get("B73973") == PENDING
    assert store.get("A89268") == DELIVERED


def test_upsert_existing_order_replaces_it(store: OrderStore) -> None:
    store.upsert(PENDING)
    store.upsert(Order("B73973", "CUST_cancel_1_refund", 124.17, "delivered"))

    assert store.get("B73973") == Order("B73973", "CUST_cancel_1_refund", 124.17, "delivered")
    assert len(store.list()) == 1


def test_set_status_changes_only_the_status(store: OrderStore) -> None:
    store.upsert(PENDING)

    store.set_status("B73973", "cancelled")

    assert store.get("B73973") == Order(
        "B73973", "CUST_cancel_1_cancel", 184.43, "cancelled", ADDRESS
    )


def test_set_status_on_unknown_order_raises(store: OrderStore) -> None:
    with pytest.raises(KeyError):
        store.set_status("nope", "cancelled")


def test_set_shipping_address_overwrites_the_address(store: OrderStore) -> None:
    store.upsert(DELIVERED)

    store.set_shipping_address("A89268", NEW_ADDRESS)

    assert store.get("A89268") == Order("A89268", "CUST_refund_0", 34.32, "delivered", NEW_ADDRESS)


def test_set_shipping_address_on_unknown_order_raises(store: OrderStore) -> None:
    with pytest.raises(KeyError):
        store.set_shipping_address("nope", NEW_ADDRESS)


def test_list_returns_every_order_sorted_by_id(store: OrderStore) -> None:
    store.upsert(PENDING)
    store.upsert(DELIVERED)

    assert store.list() == [DELIVERED, PENDING]
