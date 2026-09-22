"""Harness tests drive the vendored evaluation with a scripted stub graph; no model needed."""

import json
from pathlib import Path
from typing import Any

import pytest
from langchain_core.messages import AIMessage

from support_agent.eval.batch_evaluation import evaluate_file, load_graph, run, write_report
from support_agent.orders.store import InMemoryOrderStore, OrderStore

REFUND = {
    "sample_id": "refund_0",
    "input": [{"role": "customer", "content": "My mug arrived cracked. Refund?"}],
    "expected_function_call": {
        "name": "issue_refund",
        "arguments": {"order_id": "A89268", "amount": 34.32},
    },
    "order": {"order_id": "A89268", "total": 34.32, "status": "delivered", "customer_id": "C1"},
}
ADDRESS = {
    "name": "Customer2",
    "street1": "175 Elm St",
    "street2": "",
    "city": "Metropolis",
    "state": "CA",
    "zip": "95303",
    "country": "US",
}
MODIFY = {
    "sample_id": "modify_2",
    "input": [{"role": "customer", "content": "Ship to 175 Elm St instead?"}],
    "expected_function_call": {
        "name": "modify_order",
        "arguments": {"order_id": "C70109", "shipping_address": ADDRESS},
    },
    "order": {
        "order_id": "C70109",
        "shipping_address": ADDRESS,
        "total": 118.46,
        "status": "pending",
        "customer_id": "C2",
    },
}


class ScriptedGraph:
    """Returns the same scripted tool calls for every Scenario and records what it received."""

    def __init__(self, calls: list[dict[str, Any]], store: OrderStore | None = None) -> None:
        self.calls = calls
        self.store = store
        self.states: list[dict[str, Any]] = []
        self.orders_in_store: list[Any] = []

    def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
        self.states.append(state)
        if self.store is not None:
            self.orders_in_store.append(self.store.get(state["order"]["order_id"]))
        tool_calls = [
            {"name": c["name"], "args": c["arguments"], "id": f"call_{i}"}
            for i, c in enumerate(self.calls)
        ]
        return {
            "messages": [
                *state["messages"],
                AIMessage(content="", tool_calls=tool_calls),
                AIMessage(content="Done."),
            ]
        }


def scenario_file(tmp_path: Path, name: str, *scenarios: dict[str, Any]) -> Path:
    path = tmp_path / name
    path.write_text("".join(json.dumps(s) + "\n" for s in scenarios))
    return path


def scores_for(tmp_path: Path, calls: list[dict[str, Any]]) -> dict[str, float]:
    graph = ScriptedGraph(calls)
    [result] = evaluate_file(scenario_file(tmp_path, "one.jsonl", REFUND), lambda store: graph)
    return result.scores


def test_expected_call_scores_one_on_every_metric(tmp_path: Path) -> None:
    scores = scores_for(tmp_path, [REFUND["expected_function_call"]])

    assert scores == {
        "task_success": 1.0,
        "tool_recall": 1.0,
        "tool_precision": 1.0,
        "param_accuracy": 1.0,
        "phrase_recall": 1.0,
    }


def test_wrong_tool_scores_zero_recall(tmp_path: Path) -> None:
    scores = scores_for(tmp_path, [{"name": "cancel_order", "arguments": {"order_id": "A89268"}}])

    assert scores["tool_recall"] == 0.0


def test_extra_call_halves_precision(tmp_path: Path) -> None:
    scores = scores_for(
        tmp_path,
        [
            REFUND["expected_function_call"],
            {"name": "cancel_order", "arguments": {"order_id": "A89268"}},
        ],
    )

    assert scores["tool_precision"] == 0.5


def test_wrong_amount_scores_zero_param_accuracy(tmp_path: Path) -> None:
    scores = scores_for(
        tmp_path, [{"name": "issue_refund", "arguments": {"order_id": "A89268", "amount": 1.0}}]
    )

    assert scores["param_accuracy"] == 0.0
    assert scores["tool_recall"] == 1.0


def test_graph_receives_the_real_order_and_a_store_seeded_with_it(tmp_path: Path) -> None:
    graphs: list[ScriptedGraph] = []

    def construct(store: OrderStore) -> ScriptedGraph:
        graphs.append(ScriptedGraph([], store))
        return graphs[-1]

    evaluate_file(scenario_file(tmp_path, "two.jsonl", REFUND, MODIFY), construct)

    assert [g.states[0]["order"] for g in graphs] == [REFUND["order"], MODIFY["order"]]
    assert graphs[1].orders_in_store[0].status == "pending"
    assert graphs[1].orders_in_store[0].total == 118.46
    assert graphs[1].orders_in_store[0].shipping_address == ADDRESS
    # Each Scenario gets a fresh store: the refund order never leaks into the modify run.
    assert graphs[1].store is not None
    assert graphs[1].store.get("A89268") is None


def test_report_has_a_section_per_file_and_a_combined_section(tmp_path: Path) -> None:
    files = [
        scenario_file(tmp_path, "book.jsonl", REFUND),
        scenario_file(tmp_path, "escalation.jsonl", MODIFY),
    ]
    graph = ScriptedGraph([REFUND["expected_function_call"]])

    results = run(files, lambda store: graph)
    report = write_report(
        results, model="claude-opus-5", effort="high", reports_dir=tmp_path / "reports"
    )

    text = report.read_text()
    assert report.parent == tmp_path / "reports"
    scores = text.split("## Scores")[1].split("## Failed scenarios")[0]
    assert "| Combined | 2 |" in scores
    assert "| book.jsonl | 1 |" in scores
    assert "| escalation.jsonl | 1 |" in scores
    assert "- Model: `claude-opus-5`" in text
    assert "- Effort: `high`" in text
    # The modify Scenario failed: its expected and predicted calls appear in the failure table.
    assert "modify_2" in text
    assert "modify_order" in text
    assert "issue_refund" in text
    assert "refund_0" not in text.split("## Failed scenarios")[1]


def test_per_scenario_progress_is_printed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    graph = ScriptedGraph([REFUND["expected_function_call"]])

    evaluate_file(scenario_file(tmp_path, "two.jsonl", REFUND, MODIFY), lambda store: graph)

    out = capsys.readouterr().out
    assert "[1/2] refund_0" in out
    assert "[2/2] modify_2" in out


def test_sample_id_glob_selects_which_scenarios_run(tmp_path: Path) -> None:
    graph = ScriptedGraph([])

    path = scenario_file(tmp_path, "two.jsonl", REFUND, MODIFY)

    results = evaluate_file(path, lambda store: graph, sample_id="modify_*")

    assert [r.scenario_id for r in results] == ["modify_2"]


def test_load_graph_prefers_construct_graph_and_falls_back_to_graph(tmp_path: Path) -> None:
    with_construct = tmp_path / "with_construct.py"
    with_construct.write_text("def construct_graph(store):\n    return ('built', store)\n")
    with_graph = tmp_path / "with_graph.py"
    with_graph.write_text("graph = 'module-level'\n")
    store = InMemoryOrderStore()

    assert load_graph(with_construct)(store) == ("built", store)
    assert load_graph(with_graph)(store) == "module-level"


def test_a_crashing_graph_scores_zero_and_shows_in_the_failure_table(tmp_path: Path) -> None:
    class Crashing:
        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            raise RuntimeError("boom")

    results = run([scenario_file(tmp_path, "one.jsonl", REFUND)], lambda store: Crashing())
    report = write_report(results, model="m", effort="e", reports_dir=tmp_path / "reports")

    [result] = next(iter(results.values()))
    assert set(result.scores.values()) == {0.0}
    assert "RuntimeError('boom')" in report.read_text().split("## Failed scenarios")[1]
