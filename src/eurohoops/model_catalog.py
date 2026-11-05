"""The model catalog: every model that logs live forecasts, one entry each, in display order.

The CLI (``predict``, ``score``), the scorecard and the readers (site, API, export check) loop
over it instead of naming models. A new shadow model is one entry here plus its
``live_<id>.py`` forecast, wired into ``cli/live.py``'s ``_shadows``.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from eurohoops import config
from eurohoops.config import Competition


def _always() -> bool:
    return True


@dataclass(frozen=True)
class LiveModel:
    """One live model.

    ``tag`` is its log's ``model`` column and the file name's infix. ``name`` names it in the
    CLI's messages; ``label`` on the site and in the API (None: readers never show it).
    ``section`` is its scorecard block: the Elo ``headline``, an ``m1``-style section (log loss,
    margin and totals) or a ``trial`` section (log loss only). ``enabled`` reads the owner's
    ``<ID>_LIVE_ENABLED`` flag in ``config.py`` at call time; models without a flag are always on.
    A ``required`` model's failed forecast fails the ``predict`` run."""

    tag: str
    name: str
    label: str | None
    section: Literal["headline", "m1", "trial"]
    enabled: Callable[[], bool] = _always
    required: bool = False

    def log_path(self, comp: Competition) -> Path:
        return comp.log_path(self.tag)

    def active(self) -> bool:
        """Whether the model logs (and is read and scored): its flag, if it has one, is on."""
        return self.enabled()


ELO = LiveModel("elo", "Elo", "Our model", "headline")
CATALOG: tuple[LiveModel, ...] = (
    ELO,
    LiveModel("m1", "M1", "M1", "m1", required=True),
    LiveModel("m5", "M5", "M5", "m1"),
    LiveModel("m5inj", "M5-INJ", "M5 + injuries (trial)", "m1", lambda: config.M5INJ_LIVE_ENABLED),
    LiveModel("eloc", "ELOC", None, "trial", lambda: config.ELOC_LIVE_ENABLED),
    LiveModel(
        "eloh", "ELOH", "Elo + team home court (trial)", "trial", lambda: config.ELOH_LIVE_ENABLED
    ),
)
SHADOWS = CATALOG[1:]  # the models that log next to the Elo log


def entry(tag: str) -> LiveModel:
    """The catalog entry of model ``tag``."""
    (found,) = (m for m in CATALOG if m.tag == tag)
    return found


def active_logs(comp: Competition, *, shown: bool = False) -> dict[str, Path]:
    """Model tag -> log path of every active model, in catalog order; with ``shown``, only the
    models the readers show (those with a ``label``)."""
    return {
        m.tag: m.log_path(comp)
        for m in CATALOG
        if m.active() and (m.label is not None or not shown)
    }
