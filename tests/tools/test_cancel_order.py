"""Tool-layer tests: call a Tool by name against a seeded Order Store and assert the store state."""

import pytest

from support_agent.orders.store import Order, OrderStatus, OrderStore
from support_agent.tools import RULES, Rule, make_tools, render_rules


def cancel(store: OrderStore, order_id: str) -> dict[str, object]:
    [cancel_order] = make_tools(store)
    return cancel_order.invoke({"order_id": order_id})


def test_cancel_on_a_pending_order_sets_cancelled(store: OrderStore) -> None:
    store.upsert(Order("B1", "C1", 10.0, "pending"))

    result = cancel(store, "B1")

    assert result["allowed"] is True
    order = store.get("B1")
    assert order is not None
    assert order.status == "cancelled"


@pytest.mark.parametrize("status", ["shipped", "delivered", "cancelled", "refunded"])
def test_cancel_on_any_other_status_is_refused_with_a_message_and_leaves_the_order_unchanged(
    store: OrderStore, status: OrderStatus
) -> None:
    order = Order("B1", "C1", 10.0, status)
    store.upsert(order)

    result = cancel(store, "B1")

    assert result["allowed"] is False
    assert status in str(result["message"])
    assert store.get("B1") == order


def test_cancel_on_an_unknown_order_is_refused_without_raising(store: OrderStore) -> None:
    result = cancel(store, "NOPE")

    assert result["allowed"] is False
    assert "NOPE" in str(result["message"])


def test_a_rule_added_to_the_table_appears_in_the_rendered_rules() -> None:
    text = render_rules([*RULES, Rule("issue_refund", allowed_when="delivered", result="refunded")])

    assert "cancel_order" in text
    assert "issue_refund" in text
    assert "delivered" in text
