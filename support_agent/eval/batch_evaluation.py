"""Evaluation harness vendored from the book's ``batch_evaluation.py`` and modified (ADR 0001).

Changes from the published script: each Scenario's real ``order`` is seeded into a fresh
Order Store and passed into graph state instead of a ``pending``/``0.0`` stub; the graph is
built per Scenario through ``construct_graph(store)`` so tools act on that store; tool calls
are read from ``AIMessage.tool_calls``; Loki, weights, routing, the legacy format, and the
non-e-commerce branches are gone; several scenario files score per file and combined, and a
dated markdown report is written.

Run: ``python -m support_agent.eval.batch_evaluation --graph_py GRAPH --dataset FILE [FILE ...]
[--scenario GLOB]``
"""

import argparse
import fnmatch
import importlib.util
import json
import statistics as stats
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from support_agent.eval.metrics import param_accuracy, phrase_recall, task_success, tool_metrics
from support_agent.orders.store import InMemoryOrderStore, Order, OrderStore
from support_agent.settings import PROJECT_ROOT, load_settings

METRICS = ["task_success", "tool_recall", "tool_precision", "param_accuracy", "phrase_recall"]
DEFAULT_REPORTS_DIR = PROJECT_ROOT / "reports"

# Anything exposing LangGraph's `invoke(state) -> state`.
GraphFactory = Callable[[OrderStore], Any]
StoreFactory = Callable[[], OrderStore]


@dataclass(frozen=True)
class ScenarioResult:
    scenario_id: str
    expected: dict[str, Any]
    predicted: list[dict[str, Any]]
    scores: dict[str, float]
    error: str | None = None

    @property
    def failed(self) -> bool:
        return any(score < 1.0 for score in self.scores.values())


def to_lc_message(turn: dict):
    role = (turn.get("role") or "").lower()
    txt = turn.get("content", "")
    if role in {"customer", "user", "human"}:
        return HumanMessage(content=txt)
    if role in {"assistant", "agent", "ai"}:
        return AIMessage(content=txt)
    if role == "system":
        return SystemMessage(content=txt)
    if role == "tool":
        return ToolMessage(content=txt, tool_call_id=turn.get("tool_call_id", "unknown"))
    return HumanMessage(content=txt)


def load_graph(path: Path) -> GraphFactory:
    """Import ``path`` and return a factory building its graph over a given Order Store.

    ``construct_graph(store)`` is preferred so the graph shares the seeded store; a
    module-level ``graph`` is accepted for the book's original contract.
    """
    spec = importlib.util.spec_from_file_location("agent_graph", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "construct_graph"):
        return mod.construct_graph
    if hasattr(mod, "graph"):
        print(f"[WARN] {path} exposes only `graph`; the seeded Order Store is not shared with it")
        return lambda store: mod.graph
    raise AttributeError(f"{path} exposes neither `graph` nor `construct_graph()`")


def _text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict))


def evaluate_scenario(scenario: dict[str, Any], graph: Any) -> ScenarioResult:
    messages = [to_lc_message(t) for t in scenario["input"]]
    expected_call = scenario["expected_function_call"]
    exp_final = {
        "tool_calls": [{"tool": expected_call["name"], "params": expected_call["arguments"]}],
        "customer_msg_contains": [],
    }

    result = graph.invoke({"messages": messages, "order": scenario["order"]})

    final_reply = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_reply = _text(msg)
            break

    predicted = [
        {"name": tc["name"], "arguments": tc["args"]}
        for m in result["messages"]
        if isinstance(m, AIMessage)
        for tc in m.tool_calls
    ]
    pred_call_objs = [{"tool": c["name"], "params": c["arguments"]} for c in predicted]
    pred_tool_names = [c["name"] for c in predicted]

    tm = tool_metrics(pred_tool_names, exp_final["tool_calls"])
    return ScenarioResult(
        scenario_id=scenario["sample_id"],
        expected=expected_call,
        predicted=predicted,
        scores={
            "task_success": task_success(final_reply, pred_tool_names, exp_final),
            "tool_recall": tm["tool_recall"],
            "tool_precision": tm["tool_precision"],
            "param_accuracy": param_accuracy(pred_call_objs, exp_final["tool_calls"]),
            "phrase_recall": phrase_recall(final_reply, exp_final["customer_msg_contains"]),
        },
    )


def evaluate_file(
    path: Path,
    graph_factory: GraphFactory,
    store_factory: StoreFactory = InMemoryOrderStore,
    scenario_id: str = "*",
) -> list[ScenarioResult]:
    """Score every Scenario in ``path`` whose sample id matches the ``scenario_id`` glob.

    Each Scenario runs against a fresh store seeded with its order.
    """
    scenarios = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    scenarios = [s for s in scenarios if fnmatch.fnmatch(s["sample_id"], scenario_id)]
    results: list[ScenarioResult] = []
    for i, scenario in enumerate(scenarios, 1):
        store = store_factory()
        store.upsert(Order(**scenario["order"]))
        print(f"[{i}/{len(scenarios)}] {scenario['sample_id']} ...", end=" ", flush=True)
        try:
            result = evaluate_scenario(scenario, graph_factory(store))
        except Exception as e:
            # The book skips a crashed Scenario; we score it 0 so the report shows what broke.
            result = ScenarioResult(
                scenario_id=scenario["sample_id"],
                expected=scenario["expected_function_call"],
                predicted=[],
                scores=dict.fromkeys(METRICS, 0.0),
                error=repr(e),
            )
        print(result.error or json.dumps(result.scores), flush=True)
        results.append(result)
    return results


def run(
    files: Iterable[Path],
    graph_factory: GraphFactory,
    store_factory: StoreFactory = InMemoryOrderStore,
    scenario_id: str = "*",
) -> dict[Path, list[ScenarioResult]]:
    return {path: evaluate_file(path, graph_factory, store_factory, scenario_id) for path in files}


def combined(results: dict[Path, list[ScenarioResult]]) -> list[ScenarioResult]:
    return [r for rs in results.values() for r in rs]


def aggregate(results: list[ScenarioResult]) -> dict[str, float]:
    return {m: stats.mean(r.scores[m] for r in results) for m in METRICS} if results else {}


def format_call(call: dict[str, Any]) -> str:
    return f"`{call['name']}({json.dumps(call['arguments'], sort_keys=True)})`"


def write_report(
    results: dict[Path, list[ScenarioResult]],
    model: str,
    effort: str,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    now: datetime | None = None,
    scenario_id: str = "*",
) -> Path:
    now = now or datetime.now().astimezone()
    sections = {"Combined": combined(results), **{path.name: rs for path, rs in results.items()}}

    lines = [
        f"# Eval report {now:%Y-%m-%d %H:%M %Z}",
        "",
        f"- Model: `{model}`",
        f"- Effort: `{effort}`",
        "- phrase_recall is always 1.0 and task_success floors at 0.5: the book's scenarios "
        "carry no expected phrases.",
        f"- Scenario files: {', '.join(f'`{p}`' for p in results)}",
        f"- Scenario filter: `{scenario_id}`",
        "",
        "Scores are comparable with the book's only on the metric definitions, not on what "
        "the agent could see: this harness passes each Scenario's real order into the graph "
        "(ADR 0001).",
        "",
        "## Scores",
        "",
        "| Section | n | " + " | ".join(METRICS) + " |",
        "|---|---|" + "---|" * len(METRICS),
    ]
    for name, rs in sections.items():
        agg = aggregate(rs)
        cells = [f"{agg[m]:.3f}" if agg else "-" for m in METRICS]
        lines.append(f"| {name} | {len(rs)} | " + " | ".join(cells) + " |")

    lines += ["", "## Failed scenarios", ""]
    failed = [(path.name, r) for path, rs in results.items() for r in rs if r.failed]
    if failed:
        lines += ["| File | Scenario | Expected | Predicted |", "|---|---|---|---|"]
        for file, r in failed:
            predicted = (
                r.error or ", ".join(format_call(c) for c in r.predicted) or "(no tool call)"
            )
            lines.append(f"| {file} | {r.scenario_id} | {format_call(r.expected)} | {predicted} |")
    else:
        lines.append("None.")

    reports_dir.mkdir(parents=True, exist_ok=True)
    report = reports_dir / f"{now:%Y-%m-%d-%H%M%S}.md"
    report.write_text("\n".join(lines) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--graph_py", required=True, type=Path)
    ap.add_argument("--dataset", required=True, nargs="+", type=Path)
    ap.add_argument("--reports_dir", default=DEFAULT_REPORTS_DIR, type=Path)
    ap.add_argument("--scenario", default="*", help="glob over Scenario ids, e.g. cancel_*_cancel")
    args = ap.parse_args()

    settings = load_settings()
    results = run(args.dataset, load_graph(args.graph_py), scenario_id=args.scenario)
    report = write_report(
        results, settings.model, settings.effort, args.reports_dir, scenario_id=args.scenario
    )

    print("\n=== Aggregate scores ===")
    for m, value in aggregate(combined(results)).items():
        print(f"{m:15s}: {value:.3f}")
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()
