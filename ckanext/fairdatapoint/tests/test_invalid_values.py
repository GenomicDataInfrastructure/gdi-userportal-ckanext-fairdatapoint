# SPDX-FileCopyrightText: 2026 Health-RI
#
# SPDX-License-Identifier: Apache-2.0

"""
A harvested dataset or distribution that holds a value CKAN rejects is imported without that value.
Each dropped value is saved as a warning on the harvest object, once the import has finished.
"""

from unittest.mock import MagicMock, patch

import pytest
from ckan.plugins import toolkit

from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester


class _MinimalHarvester(CivityHarvester):
    def setup_record_provider(self, harvest_url, harvest_config_dict):
        pass

    def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
        pass


def _rejects_a_bad_number(created, returns=lambda data: data.get("id")):
    """An action that fails on number_of_records until it is dropped."""

    def action(context, data):
        if "number_of_records" in data:
            raise toolkit.ValidationError({"number_of_records": ["Invalid integer"]})
        created.append(dict(data))
        return returns(data)

    return action


@pytest.fixture
def harvester():
    instance = _MinimalHarvester()
    instance._save_object_error = MagicMock()
    return instance


def _patch_get_action(action):
    return patch("ckanext.fairdatapoint.harvesters.civity_harvester.toolkit.get_action", return_value=action)


def _patch_session():
    return patch("ckanext.fairdatapoint.harvesters.civity_harvester.model.Session")


def test_a_dataset_with_an_invalid_value_is_created_without_it(harvester):
    created = []
    package = {"id": "pkg-id", "name": "n", "title": "T", "number_of_records": "lots"}

    with _patch_get_action(_rejects_a_bad_number(created)), _patch_session():
        result = harvester._create_or_update_package(package, "create", {"user": "u"}, MagicMock())

    assert result == "pkg-id"
    assert created == [{"id": "pkg-id", "name": "n", "title": "T"}]


def test_the_warning_is_kept_until_the_import_saves_it(harvester):
    package = {"id": "pkg-id", "name": "n", "title": "T", "number_of_records": "lots"}
    warnings = []

    with _patch_get_action(_rejects_a_bad_number([])), _patch_session():
        harvester._create_or_update_package(package, "create", {"user": "u"}, MagicMock(), warnings)

    assert len(warnings) == 1
    assert "number_of_records = 'lots'" in warnings[0]
    harvester._save_object_error.assert_not_called()


def test_without_a_list_to_keep_it_in_the_warning_is_saved_at_once(harvester):
    harvest_object = MagicMock()
    package = {"id": "pkg-id", "name": "n", "title": "T", "number_of_records": "lots"}

    with _patch_get_action(_rejects_a_bad_number([])), _patch_session():
        harvester._create_or_update_package(package, "create", {"user": "u"}, harvest_object)

    message, saved_for, stage = harvester._save_object_error.call_args[0]
    assert "number_of_records = 'lots'" in message and saved_for is harvest_object and stage == "Import"


def test_the_warnings_of_one_import_do_not_reach_the_next(harvester):
    first, second = [], []
    with _patch_get_action(_rejects_a_bad_number([])), _patch_session():
        harvester._create_or_update_package(
            {"id": "a", "name": "n", "title": "T", "number_of_records": "lots"}, "create", {}, MagicMock(), first
        )
        harvester._create_or_update_package({"id": "b", "name": "m", "title": "U"}, "create", {}, MagicMock(), second)

    assert len(first) == 1 and second == []


def test_the_harvest_object_bookkeeping_is_redone_before_the_retry_of_a_create(harvester):
    harvest_object = MagicMock()
    package = {"id": "pkg-id", "name": "n", "title": "T", "number_of_records": "lots"}

    with _patch_get_action(_rejects_a_bad_number([])), _patch_session():
        harvester._create_or_update_package(package, "create", {"user": "u"}, harvest_object)

    # once before the create, once again before the retry
    assert harvest_object.add.call_count == 2
    assert harvest_object.package_id == "pkg-id"


def test_a_dataset_that_still_fails_is_reported_as_before(harvester):
    def always_fails(context, data):
        raise toolkit.ValidationError({"notes_translated": ["Missing value"]})

    package = {"id": "pkg-id", "name": "n", "title": "T"}

    with _patch_get_action(always_fails), _patch_session():
        result = harvester._create_or_update_package(package, "create", {"user": "u"}, MagicMock())

    assert result is None
    harvester._save_object_error.assert_called_once()


def test_a_resource_with_an_invalid_value_is_created_without_it_and_the_resource_is_named(harvester):
    created, warnings = [], []
    resource = {"name": "Extract", "number_of_records": "lots"}

    with _patch_get_action(_rejects_a_bad_number(created, returns=lambda data: dict(data))):
        ok = harvester._create_resources([resource], "pkg-id", "T", {"user": "u"}, MagicMock(), warnings)

    assert ok is True
    assert created == [{"name": "Extract", "package_id": "pkg-id"}]
    assert "(resource Extract)" in warnings[0]
