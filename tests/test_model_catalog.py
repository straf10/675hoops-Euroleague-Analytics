"""The model catalog's interface: one entry per live model, its log path, whether it is on."""

from dataclasses import replace
from pathlib import Path

import pytest

from eurohoops import config
from eurohoops.config import EUROLEAGUE
from eurohoops.model_catalog import CATALOG, SHADOWS, active_logs, entry

# The live logs' paths as they are on disk; a catalog change must never move them (rule 1).
LOG_PATHS = {
    "elo": "predictions/euroleague_2026-27.csv",
    "m1": "predictions/euroleague_m1_2026-27.csv",
    "m5": "predictions/euroleague_m5_2026-27.csv",
    "m5inj": "predictions/euroleague_m5inj_2026-27.csv",
    "eloc": "predictions/euroleague_eloc_2026-27.csv",
    "eloh": "predictions/euroleague_eloh_2026-27.csv",
}
FLAGS = {"m5inj": "M5INJ_LIVE_ENABLED", "eloc": "ELOC_LIVE_ENABLED", "eloh": "ELOH_LIVE_ENABLED"}


def test_every_entry_logs_where_its_log_is_today() -> None:
    assert {m.tag: m.log_path(EUROLEAGUE) for m in CATALOG} == {
        tag: Path(path) for tag, path in LOG_PATHS.items()
    }
    assert EUROLEAGUE.prediction_log == Path(LOG_PATHS["elo"])


def test_tags_are_unique_and_elo_leads() -> None:
    tags = [m.tag for m in CATALOG]
    assert len(set(tags)) == len(tags)
    assert CATALOG[0].tag == "elo" and CATALOG[0].section == "headline"
    assert all(m.section != "headline" for m in SHADOWS)
    assert entry("eloh") is CATALOG[-1]


def test_an_unknown_tag_is_an_error() -> None:
    with pytest.raises(ValueError):
        entry("nope")


def test_the_log_dir_moves_every_log(tmp_path: Path) -> None:
    comp = replace(EUROLEAGUE, log_dir=tmp_path)
    assert entry("m5").log_path(comp) == tmp_path / "euroleague_m5_2026-27.csv"


@pytest.mark.parametrize(("tag", "flag"), FLAGS.items())
def test_a_flagged_model_is_active_only_while_its_flag_is_on(
    tag: str, flag: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, flag, False)
    assert entry(tag).active() is False
    assert tag not in active_logs(EUROLEAGUE)
    monkeypatch.setattr(config, flag, True)
    assert entry(tag).active() is True
    assert active_logs(EUROLEAGUE)[tag] == Path(LOG_PATHS[tag])


def test_models_without_a_flag_are_always_active() -> None:
    assert all(entry(tag).active() for tag in ("elo", "m1", "m5"))


def test_readers_show_every_active_model_with_a_label(monkeypatch: pytest.MonkeyPatch) -> None:
    for flag in FLAGS.values():
        monkeypatch.setattr(config, flag, True)
    assert list(active_logs(EUROLEAGUE)) == list(LOG_PATHS)
    assert list(active_logs(EUROLEAGUE, shown=True)) == ["elo", "m1", "m5", "m5inj", "eloh"]


def test_m1_alone_is_required() -> None:
    assert [m.tag for m in CATALOG if m.required] == ["m1"]
