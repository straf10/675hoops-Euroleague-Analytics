"""Player crosswalk: one person_id per EuroLeague source id.

Union-find over the ``match`` overrides (one player under two EuroLeague ids). ``person_id`` is
``P:<smallest EuroLeague id>`` of the component. Every ``(competition, source_id)`` in ``names``
appears once; singletons use method ``none``.
"""

from __future__ import annotations

from collections import defaultdict

import pandas as pd
import pandera.pandas as pa

from eurohoops.parse.schemas import validated

METHODS = ("rule", "override", "pbp", "none")
COMPETITION = "euroleague"

XWALK_SCHEMA = pa.DataFrameSchema(
    {
        "person_id": pa.Column(str),
        "competition": pa.Column(str, pa.Check.isin([COMPETITION])),
        "source_id": pa.Column(str),
        "method": pa.Column(str, pa.Check.isin(list(METHODS))),
        "score": pa.Column("float64", nullable=True),
    },
    unique=["competition", "source_id"],
    strict=True,
)


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[tuple[str, str], tuple[str, str]] = {}
        self.rank: dict[tuple[str, str], int] = {}

    def add(self, node: tuple[str, str]) -> None:
        if node not in self.parent:
            self.parent[node] = node
            self.rank[node] = 0

    def find(self, node: tuple[str, str]) -> tuple[str, str]:
        self.add(node)
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, a: tuple[str, str], b: tuple[str, str]) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def _nodes_from_names(names: pd.DataFrame) -> list[tuple[str, str]]:
    keys = names[["competition", "source_id"]].drop_duplicates()
    return sorted((str(r.competition), str(r.source_id)) for r in keys.itertuples(index=False))


def _override_match_edges(
    overrides: pd.DataFrame,
) -> list[tuple[tuple[str, str], tuple[str, str]]]:
    edges: list[tuple[tuple[str, str], tuple[str, str]]] = []
    if overrides.empty:
        return edges
    for row in overrides.itertuples(index=False):
        if str(row.decision) != "match":
            continue
        a = (str(row.competition_a), str(row.source_a))
        b = (str(row.competition_b), str(row.source_b))
        edges.append((a, b))
    return edges


def _person_id(members: list[tuple[str, str]]) -> str:
    el = sorted(sid for _, sid in members)
    return f"P:{el[0]}"


def build_xwalk(names: pd.DataFrame, overrides: pd.DataFrame) -> pd.DataFrame:
    """Map every name-table source id to one person; validated against ``XWALK_SCHEMA``."""
    nodes = _nodes_from_names(names)
    uf = _UnionFind()
    for node in nodes:
        uf.add(node)

    soft = _override_match_edges(overrides)
    for a, b in soft:
        uf.union(a, b)

    groups: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for node in nodes:
        groups[uf.find(node)].append(node)

    override_nodes = {node for edge in soft for node in edge}
    rows: list[dict[str, object]] = []
    for members in groups.values():
        pid = _person_id(members)
        for comp, sid in sorted(members):
            node = (comp, sid)
            rows.append(
                {
                    "person_id": pid,
                    "competition": comp,
                    "source_id": sid,
                    "method": "override" if node in override_nodes else "none",
                    "score": float("nan"),
                }
            )
    frame = pd.DataFrame(rows, columns=list(XWALK_SCHEMA.columns))
    frame = frame.sort_values(["person_id", "competition", "source_id"]).reset_index(drop=True)
    return validated(frame, XWALK_SCHEMA)
