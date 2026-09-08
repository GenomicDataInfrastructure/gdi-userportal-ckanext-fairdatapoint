# SPDX-FileCopyrightText: 2026 Health-RI
#
# SPDX-License-Identifier: Apache-2.0

"""
`_create_or_update_package` retries a create with a freshly generated name
when it hits a `package_name_key` conflict, instead of letting the
underlying `IntegrityError` crash the harvest.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from ckanext.fairdatapoint.harvesters.civity_harvester import (
    MAX_NAME_CONFLICT_RETRIES,
    CivityHarvester,
)


class _MinimalHarvester(CivityHarvester):
    """Only the abstract methods need a body to instantiate this."""

    def setup_record_provider(self, harvest_url, harvest_config_dict):
        pass

    def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
        pass


def _name_conflict():
    return IntegrityError(
        "INSERT INTO package ...",
        {},
        Exception(
            'duplicate key value violates unique constraint "package_name_key"'
        ),
    )


def _unrelated_db_error():
    return IntegrityError(
        "INSERT INTO package ...",
        {},
        Exception('violates foreign key constraint "some_unrelated_fkey"'),
    )


@pytest.fixture
def harvester():
    return _MinimalHarvester()


@pytest.fixture
def harvest_object():
    return MagicMock()


@pytest.fixture
def package_dict():
    return {"id": "pkg-id", "name": "some-title", "title": "Some Title"}


@pytest.fixture
def context():
    return {"user": "harvest", "return_id_only": True, "ignore_auth": True}


def _patch_get_action(package_create):
    return patch(
        "ckanext.fairdatapoint.harvesters.civity_harvester.toolkit.get_action",
        return_value=package_create,
    )


def _patch_session():
    return patch("ckanext.fairdatapoint.harvesters.civity_harvester.model.Session")


class TestCreatePackageRetriesOnNameConflict:

    def test_retries_once_and_succeeds(
        self, harvester, harvest_object, package_dict, context
    ):
        calls = []

        def package_create(ctx, pkg_dict):
            calls.append(dict(pkg_dict))
            if len(calls) == 1:
                raise _name_conflict()
            return {"id": pkg_dict["id"]}

        with _patch_get_action(package_create), _patch_session(), patch.object(
            harvester, "_gen_new_name", return_value="some-title1"
        ) as gen_new_name:
            result = harvester._create_or_update_package(
                package_dict, "create", context, harvest_object
            )

        assert result == {"id": "pkg-id"}
        assert [call["name"] for call in calls] == ["some-title", "some-title1"]
        gen_new_name.assert_called_once_with("Some Title")
        # bookkeeping is redone for every attempt: the rollback after a
        # conflict wipes out whatever the previous attempt flushed.
        assert harvest_object.add.call_count == 2

    def test_gives_up_after_max_retries(
        self, harvester, harvest_object, package_dict, context
    ):
        def always_conflicts(ctx, pkg_dict):
            raise _name_conflict()

        with _patch_get_action(always_conflicts), _patch_session(), patch.object(
            harvester, "_gen_new_name", return_value="some-title-n"
        ), patch.object(harvester, "_save_object_error") as save_object_error:
            result = harvester._create_or_update_package(
                package_dict, "create", context, harvest_object
            )

        assert result is None
        save_object_error.assert_called_once()
        assert str(MAX_NAME_CONFLICT_RETRIES) in save_object_error.call_args[0][0]

    def test_reraises_errors_that_are_not_name_conflicts(
        self, harvester, harvest_object, package_dict, context
    ):
        def fails_unrelated(ctx, pkg_dict):
            raise _unrelated_db_error()

        with _patch_get_action(fails_unrelated), _patch_session():
            with pytest.raises(IntegrityError):
                harvester._create_or_update_package(
                    package_dict, "create", context, harvest_object
                )
