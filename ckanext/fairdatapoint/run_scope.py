# SPDX-FileCopyrightText: 2026 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Caches that live for one harvest job (run) and are dropped when that job is over.

Resolving labels remembers what it already learnt about a source (URIs that cannot be
loaded, languages a source does not have) so it does not ask again for every dataset. Such a
cache has to end with the harvest of that source, or it grows with every source harvested by
a long-running consumer.

A job is marked finished by another process than the one harvesting it, so there is no call
at the end of the harvest to hook into. The database is asked instead which of the jobs that
have a cache are still running.
"""
from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from typing import Any, Callable

log = logging.getLogger(__name__)

# Seconds between two checks of which harvest jobs are still running
RUN_CHECK_INTERVAL = 30

_current_run: ContextVar[str | None] = ContextVar("fairdatapoint_run", default=None)
_run_stores: dict[str, dict[str, Any]] = {}
_last_run_check = 0.0


def start_run(run_id: str | None) -> None:
    """Marks the harvest job (run) the labels are resolved for from now on

    Forgets what is cached for runs that have finished in the meantime. Without a run,
    nothing is cached per run.

    Parameters
    ----------
    run_id : str | None
        Id of the harvest job that is being harvested
    """
    forget_finished_runs(force=True)
    _current_run.set(run_id)


def current_run() -> str | None:
    """Id of the harvest job that is being harvested, None if there is none"""
    return _current_run.get()


def run_store(name: str, factory: Callable[[], Any]) -> Any | None:
    """Gets the named cache of the current run, creating it when it does not exist yet

    Parameters
    ----------
    name : str
        Name of the cache
    factory : Callable
        Creates an empty cache

    Returns
    -------
    Any | None
        The cache, or None if there is no current run
    """
    run_id = _current_run.get()
    if run_id is None:
        return None
    return _run_stores.setdefault(run_id, {}).setdefault(name, factory())


def forget_finished_runs(force: bool = False) -> None:
    """Drops the caches of every harvest job that is not running anymore

    Unless forced, the database is asked at most once every `RUN_CHECK_INTERVAL` seconds.
    The caches are kept when the database cannot be asked.
    """
    global _last_run_check

    if not _run_stores:
        return

    now = time.monotonic()
    if not force and now - _last_run_check < RUN_CHECK_INTERVAL:
        return
    _last_run_check = now

    try:
        from ckan import model
        from ckanext.harvest.model import HarvestJob

        running = {
            row[0]
            for row in model.Session.query(HarvestJob.id)
            .filter(HarvestJob.id.in_(list(_run_stores)))
            .filter(HarvestJob.status == "Running")
        }
    except Exception as e:
        log.warning("Could not check which harvest jobs are running: %s", e)
        return

    for run_id in set(_run_stores) - running:
        del _run_stores[run_id]
