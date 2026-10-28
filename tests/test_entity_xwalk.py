"""Synthetic tests for ``entity.xwalk`` (EuroLeague only: one person per EuroLeague id)."""

from __future__ import annotations

import pandas as pd

from eurohoops.entity.xwalk import XWALK_SCHEMA, build_xwalk


def _names(*source_ids: str) -> pd.DataFrame:
    return pd.DataFrame({"competition": "euroleague", "source_id": list(source_ids)})


def _override(a: str, b: str, decision: str = "match") -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "competition_a": "euroleague",
                "source_a": a,
                "competition_b": "euroleague",
                "source_b": b,
                "decision": decision,
            }
        ]
    )


def test_match_override_merges_two_el_ids_under_the_smallest() -> None:
    xwalk = build_xwalk(_names("P005983", "P005353", "P000001"), _override("P005353", "P005983"))
    merged = xwalk[xwalk["source_id"].isin(["P005353", "P005983"])]
    assert set(merged["person_id"]) == {"P:P005353"}
    assert set(merged["method"]) == {"override"}
    assert xwalk.loc[xwalk["source_id"] == "P000001", "person_id"].item() == "P:P000001"
    assert xwalk.loc[xwalk["source_id"] == "P000001", "method"].item() == "none"


def test_no_match_decision_keeps_ids_apart() -> None:
    xwalk = build_xwalk(_names("PLRU", "P012711"), _override("PLRU", "P012711", "no_match"))
    assert xwalk["person_id"].nunique() == 2
    assert set(xwalk["method"]) == {"none"}


def test_output_follows_schema_and_is_unique_per_source() -> None:
    xwalk = build_xwalk(_names("000595", "P001"), _override("P001", "000595"))
    assert list(xwalk.columns) == list(XWALK_SCHEMA.columns)
    assert not xwalk.duplicated(["competition", "source_id"]).any()
