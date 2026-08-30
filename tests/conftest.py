"""Shared fixtures.

The warehouse is built once per session, in memory. In memory because it is faster and
leaves nothing behind; once per session because building it is the expensive part and
every test here is read-only.
"""

from __future__ import annotations

import duckdb
import pytest

from sqlcookbook import warehouse


@pytest.fixture(scope="session")
def con() -> duckdb.DuckDBPyConnection:
    connection = warehouse.in_memory()
    yield connection
    connection.close()
