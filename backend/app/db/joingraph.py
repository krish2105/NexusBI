"""Per-connection join graph — discovered, not hardcoded.

The deterministic SQL synthesizer needs to know how tables join. Rather than
bake in one dataset's relationships, we build the graph per connection from the
best available source:

1. **Introspected foreign keys** (``pool.foreign_keys()``) — the real
   generalization: any Postgres / MySQL / SQLite / BigQuery warehouse that
   *declares* FK constraints gets an automatic, correct join graph.
2. **Name-based inference** — for schemas that declare no FKs (notably CSV
   uploads), infer edges from the ubiquitous ``<entity>_id → <entity>`` naming
   convention. Conservative: only when the referenced table + column actually
   exist. Augments (1) and covers pairs it misses.
3. **Curated Olist edges** — the bundled demo runs on a CSV-loaded SQLite build
   that carries no FK metadata, and its ``dates`` dimension is role-playing
   (order date vs shipping date vs review date), which pure inference can't
   disambiguate. So the demo uses a curated edge map that encodes those modeling
   choices. This is the *only* dataset-specific fallback, and it fires only when
   introspection finds nothing and the schema is recognizably Olist.

Edges from an earlier source win; later sources only ADD missing table-pairs, so
declared FKs always take precedence over inference.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.db.target_pool import TargetPool

# Curated Olist relationships (used only for the FK-less demo). One edge per
# table-pair; ``dates`` is deliberately reached via ``orders.order_date_id`` so a
# revenue-over-time series groups by *purchase* month, not shipping/review month.
OLIST_EDGES: dict[frozenset[str], str] = {
    frozenset({"order_items", "orders"}): "order_items.order_id = orders.order_id",
    frozenset({"order_items", "products"}): "order_items.product_id = products.product_id",
    frozenset({"order_items", "sellers"}): "order_items.seller_id = sellers.seller_id",
    frozenset({"products", "categories"}): "products.category_id = categories.category_id",
    frozenset({"orders", "regions"}): "orders.region_id = regions.region_id",
    frozenset({"orders", "customers"}): "orders.customer_id = customers.customer_id",
    frozenset({"orders", "dates"}): "orders.order_date_id = dates.date_id",
    frozenset({"payments", "orders"}): "payments.order_id = orders.order_id",
    frozenset({"reviews", "orders"}): "reviews.order_id = orders.order_id",
}

_OLIST_MARKERS = {"order_items", "orders"}


def _sing(t: str) -> str:
    return t[:-1] if t.endswith("s") and len(t) > 3 else t


class JoinGraph:
    """An undirected join graph: table-pair -> ON condition, with BFS pathing."""

    def __init__(self, edges: dict[frozenset[str], str], source: str = "unknown"):
        self.edges = edges
        self.source = source            # "foreign_keys" | "inferred" | "olist_curated" | "mixed" | "empty"
        self.adj: dict[str, set[str]] = {}
        for pair in edges:
            a, b = tuple(pair)
            self.adj.setdefault(a, set()).add(b)
            self.adj.setdefault(b, set()).add(a)

    def bfs_path(self, root: str, target: str) -> list[str]:
        if root == target:
            return [root]
        seen = {root}
        queue = [[root]]
        while queue:
            path = queue.pop(0)
            for nxt in sorted(self.adj.get(path[-1], ())):  # sorted = deterministic
                if nxt in seen:
                    continue
                new = path + [nxt]
                if nxt == target:
                    return new
                seen.add(nxt)
                queue.append(new)
        return []

    def plan_joins(self, required: set[str], root: str
                   ) -> tuple[str, list[str], list[str]]:
        """Return (root_table, [JOIN clauses], [unresolved tables])."""
        edges_needed: set[frozenset[str]] = set()
        unresolved: list[str] = []
        for t in required:
            if t == root:
                continue
            path = self.bfs_path(root, t)
            if not path:
                unresolved.append(t)
                continue
            for i in range(len(path) - 1):
                edges_needed.add(frozenset({path[i], path[i + 1]}))

        # Emit JOINs so each table appears only after a neighbour already in FROM.
        joins: list[str] = []
        placed = {root}
        pending = set(edges_needed)
        progress = True
        while pending and progress:
            progress = False
            for edge in sorted(pending, key=lambda e: sorted(e)):  # deterministic
                a, b = tuple(edge)
                newcomer = None
                if a in placed and b not in placed:
                    newcomer = b
                elif b in placed and a not in placed:
                    newcomer = a
                if newcomer:
                    joins.append(f"JOIN {newcomer} ON {self.edges[edge]}")
                    placed.add(newcomer)
                    pending.discard(edge)
                    progress = True
        return root, joins, unresolved


def _infer_edges(allow: dict[str, set[str]]) -> dict[frozenset[str], str]:
    """Infer ``child.<entity>_id = <entity>.<pk>`` edges from column naming."""
    tables = set(allow)
    edges: dict[frozenset[str], str] = {}
    for child, cols in allow.items():
        for col in cols:
            if not col.endswith("_id") or col == "id":
                continue
            stem = col[:-3]                       # "customer_id" -> "customer"
            for cand in (stem, stem + "s", _sing(stem)):
                if cand == child or cand not in tables:
                    continue
                pcols = allow[cand]
                ref = col if col in pcols else ("id" if "id" in pcols else None)
                if ref is None:
                    continue
                key = frozenset({child, cand})
                if key not in edges:
                    edges[key] = f"{child}.{col} = {cand}.{ref}"
                break
    return edges


def _looks_like_olist(tables: set[str]) -> bool:
    return _OLIST_MARKERS.issubset(tables)


def build_join_graph(url: str, allow: dict[str, set[str]] | None = None) -> JoinGraph:
    """Assemble the join graph for a connection from FKs, inference, and (for the
    demo) curated Olist edges. ``allow`` is the introspected {table: {cols}} map;
    fetched if not supplied."""
    from app.db.introspect import cached_allow_list

    if allow is None:
        allow = cached_allow_list(url)
    tables = set(allow)

    pool = TargetPool(url=url)
    try:
        fks = pool.foreign_keys()
    except Exception:  # noqa: BLE001 - introspection must never break generation
        fks = []

    edges: dict[frozenset[str], str] = {}
    for ft, fc, tt, tc in fks:
        if ft == tt or ft not in tables or tt not in tables:
            continue
        if fc not in allow.get(ft, set()) or tc not in allow.get(tt, set()):
            continue
        key = frozenset({ft, tt})
        edges.setdefault(key, f"{ft}.{fc} = {tt}.{tc}")

    if edges:
        # Declared FKs are authoritative; inference only fills pairs they missed.
        source = "foreign_keys"
        for key, cond in _infer_edges(allow).items():
            if key not in edges:
                edges[key] = cond
                source = "mixed"
        return JoinGraph(edges, source=source)

    # No declared FKs. The Olist demo needs its curated map (its ``dates`` role is
    # ambiguous and inference misses ``categories``), so use it verbatim for exact
    # parity. Any other FK-less schema (CSV uploads) gets pure name inference.
    if _looks_like_olist(tables):
        edges = {k: v for k, v in OLIST_EDGES.items() if set(k).issubset(tables)}
        return JoinGraph(edges, source="olist_curated")

    edges = _infer_edges(allow)
    return JoinGraph(edges, source="inferred" if edges else "empty")


@lru_cache(maxsize=8)
def cached_join_graph(url: str) -> JoinGraph:
    return build_join_graph(url)


def default_join_graph() -> JoinGraph:
    """The demo connection's graph — used when a caller supplies no graph."""
    return cached_join_graph(settings.demo_target_url)
