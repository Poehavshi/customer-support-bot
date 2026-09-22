# Customer Support Agent

An LLM-driven support agent for an e-commerce shop. See `CONTEXT.md` for the domain language and `docs/adr/` for the decisions that shape it.

## Setup

```sh
uv sync                        # install the project and dev tools on Python 3.12+
uv run pre-commit install      # ruff check --fix, ruff format, uv lock --check on every commit
cp .env.example .env           # then fill in the values; .env is git-ignored
make check                     # ruff, pyright, pytest
```
