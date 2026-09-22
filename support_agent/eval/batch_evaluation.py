"""Evaluation harness vendored from the book's ``batch_evaluation.py`` and modified (ADR 0001).

Changes from the published script: each Scenario's real ``order`` is seeded into a fresh
Order Store and passed into graph state instead of a ``pending``/``0.0`` stub; the graph is
built per Scenario through ``construct_graph(store)`` so tools act on that store; tool calls
are read from ``AIMessage.tool_calls``; Loki, weights, routing, the legacy format, and the
non-e-commerce branches are gone; several scenario files score per file and combined, and a
dated markdown report is written.

Run: ``python -m support_agent.eval.batch_evaluation --graph_py GRAPH --dataset FILE [FILE ...]``
"""

import argparse
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
    sample_id: str
    expected: dict[str, Any]
    predicted: list[dict[str, Any]]
    scores: dict[str, float]

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
    spec = importlib.util.spec_from_file_location("user_graph", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if hasattr(mod, "construct_graph"):
        return mod.construct_graph
    if hasattr(mod, "graph"):
        return lambda store: mod.graph
    raise AttributeError(f"{path} exposes neither `graph` nor `construct_graph()`")


def _text(message: AIMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content if isinstance(b, dict))


def evaluate_scenario(ex: dict[str, Any], graph: Any) -> ScenarioResult:
    messages = [to_lc_message(t) for t in ex["input"]]
    expected_call = ex["expected_function_call"]
    exp_final = {
        "tool_calls": [{"tool": expected_call["name"], "params": expected_call["arguments"]}],
        "customer_msg_contains": [],
    }

    result = graph.invoke({"messages": messages, "order": ex["order"]})

    final_reply = ""
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_reply = _text(msg)
            break

    pred_call_objs = [
        {"tool": tc["name"], "params": tc["args"]}
        for m in result["messages"]
        if isinstance(m, AIMessage)
        for tc in m.tool_calls
    ]
    pred_tool_names = [c["tool"] for c in pred_call_objs]

    tm = tool_metrics(pred_tool_names, exp_final["tool_calls"])
    return ScenarioResult(
        sample_id=ex["sample_id"],
        expected=expected_call,
        predicted=[{"name": c["tool"], "arguments": c["params"]} for c in pred_call_objs],
        scores={
            "task_success": task_success(final_reply, pred_tool_names, exp_final),
            "tool_recall": tm["tool_recall"],
            "tool_precision": tm["tool_precision"],
            "param_accuracy": param_accuracy(pred_call_objs, exp_final["tool_calls"]),
            "phrase_recall": phrase_recall(final_reply, exp_final["customer_msg_contains"]),
        },
    )


def evaluate_file(
    path: Path, graph_factory: GraphFactory, store_factory: StoreFactory = InMemoryOrderStore
) -> list[ScenarioResult]:
    """Score every Scenario in ``path``, each against a fresh store seeded with its order."""
    scenarios = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    results: list[ScenarioResult] = []
    for i, ex in enumerate(scenarios, 1):
        store = store_factory()
        store.upsert(Order(**ex["order"]))
        print(f"[{i}/{len(scenarios)}] {ex['sample_id']} ...", end=" ", flush=True)
        try:
            result = evaluate_scenario(ex, graph_factory(store))
        except Exception as e:  # the book skips a failed Scenario and carries on
            print(f"[SKIPPED] {e!r}", flush=True)
            continue
        print(json.dumps(result.scores), flush=True)
        results.append(result)
    return results


def run(
    files: Iterable[Path],
    graph_factory: GraphFactory,
    store_factory: StoreFactory = InMemoryOrderStore,
) -> dict[Path, list[ScenarioResult]]:
    return {path: evaluate_file(path, graph_factory, store_factory) for path in files}


def aggregate(results: list[ScenarioResult]) -> dict[str, float]:
    return {m: stats.mean(r.scores[m] for r in results) for m in METRICS} if results else {}


def _call(call: dict[str, Any]) -> str:
    return f"`{call['name']}({json.dumps(call['arguments'], sort_keys=True)})`"


def write_report(
    results: dict[Path, list[ScenarioResult]],
    model: str,
    effort: str,
    reports_dir: Path = DEFAULT_REPORTS_DIR,
    now: datetime | None = None,
) -> Path:
    now = now or datetime.now().astimezone()
    combined = [r for rs in results.values() for r in rs]
    sections = {"Combined": combined, **{path.name: rs for path, rs in results.items()}}

    lines = [
        f"# Eval report {now:%Y-%m-%d %H:%M %Z}",
        "",
        f"- Model: `{model}`",
        f"- Effort: `{effort}`",
        f"- Scenario files: {', '.join(f'`{p}`' for p in results)}",
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
            predicted = ", ".join(_call(c) for c in r.predicted) or "(no tool call)"
            lines.append(f"| {file} | {r.sample_id} | {_call(r.expected)} | {predicted} |")
    else:
        lines.append("None.")

    reports_dir.mkdir(parents=True, exist_ok=True)
    report = reports_dir / f"{now:%Y-%m-%d-%H%M}.md"
    report.write_text("\n".join(lines) + "\n")
    return report


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--graph_py", required=True, type=Path)
    ap.add_argument("--dataset", required=True, nargs="+", type=Path)
    ap.add_argument("--reports_dir", default=DEFAULT_REPORTS_DIR, type=Path)
    args = ap.parse_args()

    settings = load_settings()
    results = run(args.dataset, load_graph(args.graph_py))
    report = write_report(results, settings.model, settings.effort, args.reports_dir)

    print("\n=== Aggregate scores ===")
    for m, value in aggregate([r for rs in results.values() for r in rs]).items():
        print(f"{m:15s}: {value:.3f}")
    print(f"\nReport: {report}")


if __name__ == "__main__":
    main()
