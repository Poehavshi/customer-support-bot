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
## FILTER is a glob over sample ids; only the plain cancel Scenarios until the other Tools land.
## Override with `make eval FILTER='*'` or `make eval GRAPH=...`. Needs ANTHROPIC_API_KEY in .env.
GRAPH ?= support_agent/agent/graph.py
FILTER ?= cancel_*_cancel
eval:
	uv run python -m support_agent.eval.batch_evaluation --graph_py $(GRAPH) --dataset support_agent/eval/scenarios/*.jsonl --sample_id '$(FILTER)'

## Apply the Order Store schema and upsert the scenario orders plus hand-written extras. Idempotent.
seed:
	uv run python -m support_agent.orders.seed

## Stub for a later ticket. Prints what it will do.
ui:
	@echo "make ui: will start the Streamlit UI against the compose Postgres and the configured Helpdesk."
