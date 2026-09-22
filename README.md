# Customer Support Agent

An LLM-driven support agent for an e-commerce shop. See `CONTEXT.md` for the domain language and `docs/adr/` for the decisions that shape it.

## Setup

```sh
uv sync                        # install the project and dev tools on Python 3.12+
uv run pre-commit install      # ruff check --fix, ruff format, uv lock --check on every commit
cp .env.example .env           # then fill in the values; .env is git-ignored
make check                     # ruff, pyright, pytest
```

## Order Store

```sh
docker compose up -d --wait postgres   # PostgreSQL on 5432; POSTGRES_PORT=5433 if that port is taken
make seed                              # apply the schema and upsert the scenario orders plus extras; safe to re-run
```

The schema is one SQL file, `support_agent/orders/schema.sql`, applied on startup. The seed loads
every order from the book's vendored scenario file plus hand-written orders in `shipped`, `cancelled`,
and `refunded` status. Tests run the same contract suite against the in-memory store and, when
`DATABASE_URL` is set, against Postgres. The Postgres tests truncate the `orders` table, so run
`make seed` again after `make check` if you want the seeded rows back.
