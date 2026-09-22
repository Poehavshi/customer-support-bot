"""Metric functions vendored from the book's ``src/common/evaluation/metrics.py`` (ADR 0001).

The four functions the e-commerce harness uses are kept byte-for-byte so scores stay
comparable with the book's. The bert-score and sentence-transformers metrics are dropped.
"""

# ruff: noqa: UP006, UP035
from typing import Dict, List


def phrase_recall(pred_reply: str, phrases: List[str]) -> float:
    if not phrases:
        return 1.0
    found = sum(1 for p in phrases if p.lower() in pred_reply.lower())
    return found / len(phrases)


def tool_metrics(pred_tools: List[str], expected_calls: List[dict]) -> Dict[str, float]:
    expected_names = [c.get("tool") for c in expected_calls]
    if not expected_names:
        return {"tool_recall": 1.0, "tool_precision": 1.0}
    pred_set = set(pred_tools)
    exp_set = set(expected_names)
    tp = len(exp_set & pred_set)
    recall = tp / len(exp_set)
    precision = tp / len(pred_set) if pred_set else 0.0
    return {"tool_recall": recall, "tool_precision": precision}


def param_accuracy(pred_calls: List[dict], expected_calls: List[dict]) -> float:
    if not expected_calls:
        return 1.0
    matched = 0
    for exp in expected_calls:
        for pred in pred_calls:
            if pred.get("tool") == exp.get("tool") and pred.get("params") == exp.get("params"):
                matched += 1
                break
    return matched / len(expected_calls)


def task_success(pred_reply: str, pred_tools: List[str], expected: dict) -> float:
    pr = phrase_recall(pred_reply, expected.get("customer_msg_contains", []))
    tr = tool_metrics(pred_tools, expected.get("tool_calls", [])).get("tool_recall", 0.0)
    return (pr + tr) / 2.0
