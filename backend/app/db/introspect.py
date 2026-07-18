"""Schema introspection -> allow-list and column metadata.

The allow-list is derived from the *live* target schema on connect, so it always
matches reality (and hallucinated identifiers are rejected for free).
"""
from __future__ import annotations

from functools import lru_cache

from app.db.target_pool import TargetPool
from app.sqlsafety import AllowList


def build_allow_list(pool: TargetPool | None = None) -> AllowList:
    pool = pool or TargetPool()
    allow: AllowList = {}
    for table in pool.list_tables():
        cols = {name.lower() for name, _type in pool.table_columns(table)}
        allow[table.lower()] = cols
    return allow


@lru_cache(maxsize=8)
def cached_allow_list(url: str) -> AllowList:
    return build_allow_list(TargetPool(url=url))
