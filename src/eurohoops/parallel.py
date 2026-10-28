"""Process-level parallelism for the per-game export work, with results in input order.

Each game's file is read and computed on its own, so the export splits the games over worker
processes and combines the results in the order it was given (the callers pass the games sorted by
id). ``EUROHOOPS_WORKERS`` sets the number of workers (1 runs everything in-process); the default
is the CPU count, capped at four so a GitHub runner and a laptop use the same few cores.

``fn`` must be a module-level function and its items picklable (spawn-safe on Windows). Shared
state a worker needs (a fitted model) comes from ``initializer``, run once per worker process.
"""

import os
from collections.abc import Callable, Hashable, Iterable, Mapping
from concurrent.futures import ProcessPoolExecutor
from types import SimpleNamespace
from typing import Any

WORKERS_ENV = "EUROHOOPS_WORKERS"
MAX_WORKERS = 4
MIN_PARALLEL_ITEMS = 100  # a pool's start-up costs more than it saves on a few games


def record(row: Mapping[Hashable, Any]) -> SimpleNamespace:
    """A table row (``to_dict("records")``) as a namespace with string keys, which pickles."""
    return SimpleNamespace(**{str(key): value for key, value in row.items()})


def workers() -> int:
    """The worker count: ``EUROHOOPS_WORKERS`` if set, else the CPU count capped at four."""
    raw = os.environ.get(WORKERS_ENV, "").strip()
    if raw:
        return max(1, int(raw))
    return max(1, min(MAX_WORKERS, os.cpu_count() or 1))


def map_ordered[T, R](
    fn: Callable[[T], R],
    items: Iterable[T],
    initializer: Callable[..., None] | None = None,
    initargs: tuple[Any, ...] = (),
) -> list[R]:
    """``[fn(item) for item in items]``, computed in worker processes when there are enough."""
    batch = list(items)
    count = min(workers(), len(batch) // MIN_PARALLEL_ITEMS)
    if count <= 1:
        if initializer is not None:
            initializer(*initargs)
        return [fn(item) for item in batch]
    chunk = max(1, len(batch) // (count * 4))
    with ProcessPoolExecutor(max_workers=count, initializer=initializer, initargs=initargs) as pool:
        return list(pool.map(fn, batch, chunksize=chunk))
