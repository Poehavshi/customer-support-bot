"""Tools: the fixed actions the Support Agent may take on an Order, and the rule table they enforce.

The same table renders into the system prompt, so the prompt's statement of the rules and
the tool code cannot drift apart. A Tool never raises for a rule violation: it returns a
structured allowed-or-refused result that the agent turns into the customer reply.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import TypedDict

from langchain_core.tools import BaseTool, tool

from support_agent.orders.store import OrderStatus, OrderStore


@dataclass(frozen=True)
class Rule:
    tool: str
    allowed_when: OrderStatus
    result: OrderStatus


RULES = [Rule("cancel_order", allowed_when="pending", result="cancelled")]


class ToolResult(TypedDict):
    allowed: bool
    message: str


def render_rules(rules: Iterable[Rule] = RULES) -> str:
    return "\n".join(
        f"- `{r.tool}` is allowed only while the order status is `{r.allowed_when}`;"
        f" afterwards the status is `{r.result}`."
        for r in rules
    )


def _apply(store: OrderStore, rule: Rule, order_id: str) -> ToolResult:
    """Enforce ``rule`` on the order and move it to the rule's result status when allowed."""
    order = store.get(order_id)
    if order is None:
        return ToolResult(allowed=False, message=f"Order {order_id} was not found.")
    if order.status != rule.allowed_when:
        return ToolResult(
            allowed=False,
            message=f"Order {order_id} is {order.status}, and {rule.tool} is only allowed"
            f" while it is {rule.allowed_when}. The order is unchanged.",
        )
    store.set_status(order_id, rule.result)
    return ToolResult(allowed=True, message=f"Order {order_id} is now {rule.result}.")


def make_tools(store: OrderStore) -> list[BaseTool]:
    """The Tools, bound to ``store``. Names and argument shapes match the evaluation set."""
    rules = {rule.tool: rule for rule in RULES}

    @tool
    def cancel_order(order_id: str) -> ToolResult:
        """Cancel the customer's order. Allowed only while the order is pending."""
        return _apply(store, rules["cancel_order"], order_id)

    return [cancel_order]
