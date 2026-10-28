"""The ordered process map (parallel.py): the same results in the same order as a plain loop."""

import operator

import pytest

from eurohoops import parallel


def test_worker_count_follows_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(parallel.WORKERS_ENV, "3")
    assert parallel.workers() == 3
    monkeypatch.setenv(parallel.WORKERS_ENV, "0")
    assert parallel.workers() == 1  # never below one
    monkeypatch.delenv(parallel.WORKERS_ENV)
    assert 1 <= parallel.workers() <= parallel.MAX_WORKERS


def test_results_keep_the_input_order_in_worker_processes(monkeypatch: pytest.MonkeyPatch) -> None:
    items = list(range(3 * parallel.MIN_PARALLEL_ITEMS))
    monkeypatch.setenv(parallel.WORKERS_ENV, "1")
    serial = parallel.map_ordered(operator.neg, items)
    monkeypatch.setenv(parallel.WORKERS_ENV, "2")  # enough items to start a pool
    assert parallel.map_ordered(operator.neg, items) == serial == [-i for i in items]


def test_a_few_items_run_in_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(parallel.WORKERS_ENV, "4")
    assert parallel.map_ordered(operator.neg, [1, 2]) == [-1, -2]
