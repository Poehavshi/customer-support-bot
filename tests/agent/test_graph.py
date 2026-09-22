"""Graph tests drive the Support Agent with a scripted fake model; no API key needed."""

from collections.abc import Sequence
from typing import Any, cast

from langchain_core.language_models import LanguageModelInput
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from support_agent.agent.graph import construct_graph, system_prompt
from support_agent.orders.store import InMemoryOrderStore, Order
from support_agent.tools import RULES, Rule

CANCEL = {"name": "cancel_order", "args": {"order_id": "B1"}, "id": "call_1"}


class ScriptedModel(GenericFakeChatModel):
    """Replies with the scripted messages in order, whatever tools are bound."""

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Any | BaseTool],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        return cast(Runnable[LanguageModelInput, AIMessage], self)


def run(store: InMemoryOrderStore, *replies: AIMessage) -> list[BaseMessage]:
    graph = construct_graph(store, model=ScriptedModel(messages=iter(replies)))
    result = graph.invoke(
        {"messages": [HumanMessage("Please cancel it.")], "order": {"order_id": "B1"}}
    )
    return result["messages"]


def pending_store() -> InMemoryOrderStore:
    store = InMemoryOrderStore()
    store.upsert(Order("B1", "C1", 10.0, "pending"))
    return store


def test_one_tool_call_is_executed_and_followed_by_one_reply() -> None:
    store = pending_store()

    messages = run(
        store, AIMessage(content="", tool_calls=[CANCEL]), AIMessage(content="Done, cancelled.")
    )

    assert [type(m) for m in messages] == [HumanMessage, AIMessage, ToolMessage, AIMessage]
    assert messages[-1].content == "Done, cancelled."
    order = store.get("B1")
    assert order is not None
    assert order.status == "cancelled"


def test_a_run_never_executes_two_tool_calls_even_if_the_model_keeps_asking() -> None:
    store = pending_store()
    again = AIMessage(content="", tool_calls=[{**CANCEL, "id": "call_2"}])
    more = AIMessage(content="", tool_calls=[{**CANCEL, "id": "call_3"}])

    messages = run(store, AIMessage(content="", tool_calls=[CANCEL]), again, more)

    assert sum(isinstance(m, ToolMessage) for m in messages) == 1
    assert len(messages) == 4


def test_a_reply_without_a_tool_call_ends_the_run() -> None:
    messages = run(pending_store(), AIMessage(content="Which order do you mean?"))

    assert [type(m) for m in messages] == [HumanMessage, AIMessage]


def test_the_prompt_renders_the_order_and_every_rule_in_the_table() -> None:
    order = Order("B1", "C1", 12.5, "pending")

    text = system_prompt(order, [*RULES, Rule("issue_refund", "delivered", "refunded")])

    assert "B1" in text
    assert "pending" in text
    assert "12.5" in text
    assert "issue_refund" in text
