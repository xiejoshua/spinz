"""Shared pytest fixtures for the auxd-api test suite.

Beanie's ``Document.__init__`` calls ``get_pymongo_collection()``, which
raises ``CollectionWasNotInitialized`` unless ``init_beanie()`` has wired
the model class to a database. That makes pure unit tests of Document
*shape* (no DB writes) impossible without an init step.

We solve this once, here, with an autouse session fixture that:

1. Spins up an in-memory MongoDB via ``mongomock-motor`` (no real Mongo
   process required — pure Python).
2. Registers every Beanie Document the codebase defines so that any
   test in the suite can instantiate them. The list is sourced from
   :data:`auxd_api.db.ALL_DOCUMENT_MODELS` — one source of truth for both
   production and tests.

The mock database is shared across the whole session because Beanie's
init is global and a per-test reset would slow tests down. Tests that
need write isolation should use ``Model.delete_all()`` in their own
setup — at MVP, no test writes to the mock DB (all are field-shape
assertions).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient

from auxd_api.db import ALL_DOCUMENT_MODELS


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _initialize_beanie_for_tests() -> AsyncIterator[None]:
    """Initialize Beanie against an in-memory mongomock database once per
    test session. Documents can then be instantiated freely; the mock
    DB accepts (and discards) any writes if a test happens to do them.
    """
    client: AsyncMongoMockClient[dict[str, object]] = AsyncMongoMockClient()
    database = client["auxd_test"]
    await init_beanie(database=database, document_models=list(ALL_DOCUMENT_MODELS))
    yield
    # mongomock-motor has no explicit teardown; the client is GC'd.


@pytest.fixture
def anyio_backend() -> str:
    """If any test opts into anyio instead of pytest-asyncio, default to asyncio."""
    return "asyncio"
