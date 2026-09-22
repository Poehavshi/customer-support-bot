.PHONY: check lint typecheck test eval seed ui

## Run every quality gate: ruff, pyright, pytest. Exits non-zero on the first failure.
check: lint typecheck test

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run pyright

test:
	uv run pytest

## Run the evaluation harness over every scenario file and write a dated report under reports/.
## GRAPH is the agent module; override with `make eval GRAPH=path/to/graph.py`.
GRAPH ?= support_agent/agent/graph.py
eval:
	uv run python -m support_agent.eval.batch_evaluation --graph_py $(GRAPH) --dataset support_agent/eval/scenarios/*.jsonl

## Apply the Order Store schema and upsert the scenario orders plus hand-written extras. Idempotent.
seed:
	uv run python -m support_agent.orders.seed

## Stub for a later ticket. Prints what it will do.
ui:
	@echo "make ui: will start the Streamlit UI against the compose Postgres and the configured Helpdesk."
