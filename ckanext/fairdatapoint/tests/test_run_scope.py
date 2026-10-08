# SPDX-FileCopyrightText: 2026 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Caches that live for one harvest job and are dropped when it is not running anymore."""
from unittest.mock import patch

import pytest

from ckanext.fairdatapoint import run_scope
from ckanext.fairdatapoint.run_scope import (
    current_run,
    forget_finished_runs,
    run_store,
    start_run,
)


@pytest.fixture(autouse=True)
def clean_state():
    run_scope._run_stores.clear()
    run_scope._current_run.set(None)
    run_scope._last_run_check = 0.0
    yield
    run_scope._run_stores.clear()
    run_scope._current_run.set(None)
    run_scope._last_run_check = 0.0


def _jobs_running(session, *job_ids):
    session.query.return_value.filter.return_value.filter.return_value = [
        (job_id,) for job_id in job_ids
    ]


class TestRunStore:
    def test_there_is_no_store_without_a_run(self):
        assert run_store("names", set) is None

    def test_a_run_gets_the_same_store_every_time(self):
        start_run("job-1")

        first = run_store("names", set)
        first.add("a")

        assert run_store("names", set) is first
        assert run_store("names", set) == {"a"}

    def test_stores_of_different_names_are_separate(self):
        start_run("job-1")

        run_store("names", set).add("a")

        assert run_store("other", set) == set()

    def test_runs_do_not_share_stores(self):
        start_run("job-1")
        run_store("names", set).add("a")

        start_run("job-2")

        assert run_store("names", set) == set()
        assert current_run() == "job-2"

    def test_a_run_of_none_has_no_store(self):
        start_run("job-1")
        start_run(None)

        assert current_run() is None
        assert run_store("names", set) is None


class TestForgetFinishedRuns:
    @patch("ckan.model.Session")
    def test_runs_that_are_not_running_anymore_are_forgotten(self, session):
        run_scope._run_stores.update({"job-1": {"names": set()}, "job-2": {"names": set()}})
        _jobs_running(session, "job-2")

        forget_finished_runs(force=True)

        assert list(run_scope._run_stores) == ["job-2"]

    @patch("ckan.model.Session")
    def test_starting_a_run_forgets_finished_runs(self, session):
        run_scope._run_stores["job-1"] = {"names": {"a"}}
        _jobs_running(session)

        start_run("job-2")

        assert run_scope._run_stores == {}

    @patch("ckan.model.Session")
    def test_the_database_is_not_asked_when_nothing_is_cached(self, session):
        forget_finished_runs(force=True)

        session.query.assert_not_called()

    @patch("ckan.model.Session")
    def test_the_check_is_throttled(self, session):
        run_scope._run_stores["job-1"] = {"names": set()}
        _jobs_running(session)

        forget_finished_runs()
        run_scope._run_stores["job-1"] = {"names": set()}
        forget_finished_runs()

        assert session.query.call_count == 1
        assert "job-1" in run_scope._run_stores

    @patch("ckan.model.Session")
    def test_a_forced_check_ignores_the_throttle(self, session):
        run_scope._run_stores["job-1"] = {"names": set()}
        _jobs_running(session)

        forget_finished_runs()
        run_scope._run_stores["job-1"] = {"names": set()}
        forget_finished_runs(force=True)

        assert session.query.call_count == 2
        assert run_scope._run_stores == {}

    @patch("ckan.model.Session")
    def test_the_cache_is_kept_when_the_database_cannot_be_asked(self, session):
        run_scope._run_stores["job-1"] = {"names": set()}
        session.query.side_effect = RuntimeError("database down")

        forget_finished_runs(force=True)

        assert "job-1" in run_scope._run_stores

    @patch("ckan.model.Session")
    def test_the_same_run_does_not_ask_the_database_again(self, session):
        run_scope._run_stores["job-1"] = {"names": set()}
        _jobs_running(session, "job-1")

        for _ in range(3):
            start_run("job-1")

        # asked when the run began, not again for every record of it
        assert session.query.call_count == 1

    @patch("ckan.model.Session")
    def test_a_finished_current_run_is_left_and_not_recreated(self, session):
        start_run("job-1")
        run_store("names", set).add("a")
        _jobs_running(session)

        forget_finished_runs(force=True)

        assert current_run() is None
        assert run_store("names", set) is None
        assert run_scope._run_stores == {}

    @patch("ckan.model.Session")
    def test_a_running_current_run_is_kept(self, session):
        start_run("job-1")
        run_store("names", set).add("a")
        _jobs_running(session, "job-1")

        forget_finished_runs(force=True)

        assert current_run() == "job-1"
        assert run_store("names", set) == {"a"}
