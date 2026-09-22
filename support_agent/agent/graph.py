"""Support Agent: a LangGraph graph over Claude that acts on one Order through the Tools (ADR 0003).

Shape: assistant -> tools -> reply -> END, so a run makes at most one tool call. The order is
read from the Order Store at the start of the run and rendered into the system prompt; there
is no lookup tool (ADR 0002).
"""

from collections.abc import Iterable
from typing import Annotated, Any, Literal, TypedDict, cast

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import SecretStr

from support_agent.orders.store import InMemoryOrderStore, Order, OrderStore
from support_agent.settings import load_settings
from support_agent.tools import RULES, Rule, make_tools, render_rules


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    order: dict[str, Any]
    """The order the conversation is about; only ``order_id`` is read, the rest is in the store."""


def system_prompt(order: Order, rules: Iterable[Rule] = RULES) -> str:
    address = order.shipping_address
    address_text = ", ".join(str(v) for v in address.values() if v) if address else "not on file"
    return f"""You are the customer support agent for an online shop. The customer is writing about
exactly one order, shown below. Act only on this order; never guess at another one.

Order:
- id: {order.order_id}
- status: {order.status}
- total: {order.total:.2f}
- shipping address: {address_text}

Rules, enforced by the tools:
{render_rules(rules)}

Take at most one action per customer message. When the customer asks for something a tool
allows, call the tool. After the tool result, reply to the customer in plain language confirming
what happened, or explaining why nothing was done."""


def default_model() -> BaseChatModel:
    settings = load_settings()
    effort = None if settings.effort == "default" else settings.effort
    return ChatAnthropic(
        model_name=settings.model,
        effort=cast(Literal["max", "xhigh", "high", "medium", "low"] | None, effort),
        api_key=SecretStr(settings.anthropic_api_key or ""),
        base_url=settings.anthropic_base_url,
        # pyright sees these pydantic aliases as required; the values are the library defaults.
        timeout=None,
        stop=None,
    )


def construct_graph(
    store: OrderStore, helpdesk: object = None, model: BaseChatModel | None = None
) -> Any:
    """Build the agent over ``store``. ``helpdesk`` is unused until escalation lands."""
    model = model or default_model()
    tools = make_tools(store)
    act = model.bind_tools(tools, parallel_tool_calls=False)
    # The reply turn cannot call a tool, so a run makes at most one.
    reply = model.bind_tools(tools, tool_choice=cast(Any, {"type": "none"}))

    def prompt(state: State) -> list[AnyMessage]:
        order = store.get(state["order"]["order_id"])
        if order is None:
            raise KeyError(state["order"]["order_id"])
        return [SystemMessage(system_prompt(order)), *state["messages"]]

    def assistant(state: State) -> dict[str, Any]:
        return {"messages": [act.invoke(prompt(state))]}

    def assistant_reply(state: State) -> dict[str, Any]:
        return {"messages": [reply.invoke(prompt(state))]}

    def after_assistant(state: State) -> str:
        last = state["messages"][-1]
        return "tools" if getattr(last, "tool_calls", None) else END

    graph = StateGraph(State)
    graph.add_node("assistant", assistant)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("reply", assistant_reply)
    graph.add_edge(START, "assistant")
    graph.add_conditional_edges("assistant", after_assistant, ["tools", END])
    graph.add_edge("tools", "reply")
    graph.add_edge("reply", END)
    return graph.compile()


def __getattr__(name: str) -> Any:
    # The book's contract: a module-level `graph` with default dependencies, built on first use
    # so importing this module needs no API key.
    if name == "graph":
        return construct_graph(InMemoryOrderStore())
    raise AttributeError(name)
