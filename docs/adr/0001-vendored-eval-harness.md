# Vendor and modify the book's evaluation harness

The evaluation set and `batch_evaluation.py` come from *Building Applications with AI Agents* (michaelalbada). The script as published discards the scenario's `order` and invokes the graph with a stub order (status `pending`, total `0.0`, no address), so the delivered-order cancel cases, every refund amount, and every address change can never score. It also imports a Loki logger and a metrics module that loads bert-score and sentence-transformers at import time, none of which the e-commerce scenarios use. We copy the harness into `support_agent/eval/`, pass the real scenario order into the graph state, and strip the unused imports, while keeping the metric functions byte-for-byte so scores stay comparable with the book's.

## Consequences

- Scores are comparable with the book only on the metric definitions, not on what the agent could see. Say so in every eval report.
- Upstream changes to the harness are not tracked; re-vendor deliberately.
