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

## Stubs for later tickets. Each prints what it will do.
eval:
	@echo "make eval: will run the evaluation harness over the scenario files and write a dated report under reports/."

seed:
	@echo "make seed: will apply the Order Store schema and load the 31 scenario orders plus hand-written extras into Postgres."

ui:
	@echo "make ui: will start the Streamlit UI against the compose Postgres and the configured Helpdesk."
