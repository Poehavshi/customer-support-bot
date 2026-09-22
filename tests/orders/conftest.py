from collections.abc import Iterator

import psycopg
import pytest

from support_agent.orders.store import InMemoryOrderStore, OrderStore, PostgresOrderStore
from support_agent.settings import load_settings


@pytest.fixture(params=["memory", "postgres"])
def store(request: pytest.FixtureRequest) -> Iterator[OrderStore]:
    """One empty Order Store per test, for each implementation.

    The Postgres case needs DATABASE_URL (compose locally, the service container in CI).
    """
    if request.param == "memory":
        yield InMemoryOrderStore()
        return
    url = load_settings().database_url
    if not url:
        pytest.skip("DATABASE_URL is not set")
    store = PostgresOrderStore(url)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("TRUNCATE orders")
    yield store
    store.close()
