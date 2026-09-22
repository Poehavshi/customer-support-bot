from collections import Counter

from support_agent.orders.seed import scenario_orders, seed
from support_agent.orders.store import Order, OrderStore


def test_seed_is_idempotent(store: OrderStore) -> None:
    seed(store)
    first = store.list()

    seed(store)

    assert store.list() == first


def test_seed_holds_every_scenario_order_id_and_the_hand_written_extras(
    store: OrderStore,
) -> None:
    seed(store)
    ids = {order.order_id for order in store.list()}

    assert {order.order_id for order in scenario_orders()} <= ids
    # Eight scenario pairs share an order id; the later, delivered variant wins.
    assert store.get("B73973") == Order("B73973", "CUST_cancel_1_refund", 124.17, "delivered")
    statuses = Counter(order.status for order in store.list())
    assert statuses["shipped"] >= 2
    assert statuses["cancelled"] >= 2
    assert statuses["refunded"] >= 2


def test_scenario_orders_come_from_the_vendored_book_file() -> None:
    orders = scenario_orders()

    assert len(orders) == 32
    assert orders[0].order_id == "A89268"
    assert orders[0].total == 34.32
    assert orders[0].status == "delivered"
    addressed = [order for order in orders if order.shipping_address is not None]
    assert len(addressed) == 8
    assert set(addressed[0].shipping_address or {}) == {
        "name",
        "street1",
        "street2",
        "city",
        "state",
        "zip",
        "country",
    }
