# SPDX-FileCopyrightText: 2025 Health-RI
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import patch, MagicMock

from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester
from ckanext.harvest.model import HarvestObjectExtra as HOExtra


@pytest.fixture
def mock_harvest_source():
    source = MagicMock()
    source.id = "civity-source-id"
    source.url = "http://dummy-url.com"
    source.config = None
    source.owner_org = "org-id"
    return source


@pytest.fixture
def mock_harvest_job(mock_harvest_source):
    job = MagicMock()
    job.id = "harvest-job-1"
    job.source = mock_harvest_source
    return job


@pytest.fixture
def harvest_object(mock_harvest_source, mock_harvest_job):
    obj = MagicMock()
    obj.id = "harvest-123"
    obj.guid = "dataset=https://fdp.example.org/dataset/abc"
    obj.extras = [HOExtra(key="status", value="new")]
    obj.content = None
    obj.save = MagicMock()
    obj.source = mock_harvest_source
    obj.job = mock_harvest_job
    return obj

@pytest.fixture
def dummy_harvester():
    class DummyFDPHarvester(CivityHarvester):
        def setup_record_provider(self, harvest_url, harvest_config_dict):
            self.record_provider = MagicMock()
            self.record_provider.get_record_by_id = MagicMock()

        def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
            pass  # Not needed for gather stage

    return DummyFDPHarvester()

@pytest.fixture
def configurable_harvester():
    def _create(record_return_value):
        class DummyFDPHarvester(CivityHarvester):
            def setup_record_provider(self, url, config):
                self.record_provider = MagicMock()
                self.record_provider.get_record_by_id = MagicMock(return_value=record_return_value)

            def setup_record_to_package_converter(self, url, config):
                pass
        return DummyFDPHarvester()
    return _create

@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HOExtra")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HarvestObject")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.model.Session.query")
def test_gather_stage_creates_new_object(mock_query, mock_HO, mock_HOExtra, dummy_harvester, mock_harvest_job):
    dummy_harvester._get_guids_in_harvest = lambda job: {"new-guid"}
    dummy_harvester._get_guids_to_package_ids_from_database = lambda job: {}

    mock_query.return_value.filter_by.return_value.first.return_value = None

    ho_extra_mock = MagicMock()
    mock_HOExtra.return_value = ho_extra_mock

    mock_obj = MagicMock(id="obj-new-guid")
    mock_HO.return_value = mock_obj

    result = dummy_harvester.gather_stage(mock_harvest_job)

    assert result == ["obj-new-guid"]
    mock_HOExtra.assert_called_once_with(key="status", value="new")
    mock_HO.assert_called_once_with(
        guid="new-guid",
        job=mock_harvest_job,
        extras=[ho_extra_mock],
    )

@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HOExtra")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HarvestObject")
def test_gather_stage_creates_change_object(mock_HO, mock_HOExtra, dummy_harvester, mock_harvest_job):
    dummy_harvester._get_guids_in_harvest = lambda job: {"change-guid"}
    dummy_harvester._get_guids_to_package_ids_from_database = lambda job: {
        "change-guid": "pkg-1"
    }

    mock_HOExtra.return_value = "Extra(status=change)"

    mock_obj = MagicMock(id="obj-change-guid")
    mock_HO.return_value = mock_obj

    result = dummy_harvester.gather_stage(mock_harvest_job)

    assert result == ["obj-change-guid"]
    mock_HOExtra.assert_called_once_with(key="status", value="change")
    mock_HO.assert_called_once_with(
        guid="change-guid",
        job=mock_harvest_job,
        package_id="pkg-1",
        extras=["Extra(status=change)"]
    )

@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HOExtra")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HarvestObject")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.model.Session.query")
def test_gather_stage_creates_delete_object_and_marks_not_current(mock_query, mock_HO, mock_HOExtra, dummy_harvester, mock_harvest_job):

    # Setup GUIDs
    change_guid = "guid-to-change"
    delete_guid = "guid-to-delete"

    dummy_harvester._get_guids_in_harvest = lambda job: {change_guid}
    dummy_harvester._get_guids_to_package_ids_from_database = lambda job: {
        change_guid: "pkg-change",
        delete_guid: "pkg-delete"
    }

    # Prepare HOExtra mocks
    hoextra_change = MagicMock()
    hoextra_delete = MagicMock()

    def hoextra_side_effect(key, value):
        return hoextra_change if value == "change" else hoextra_delete

    mock_HOExtra.side_effect = hoextra_side_effect

    # Prepare HarvestObject mocks
    ho_change = MagicMock(id="ho-change")
    ho_delete = MagicMock(id="ho-delete")

    def ho_side_effect(**kwargs):
        if kwargs["guid"] == change_guid:
            return ho_change
        else:
            return ho_delete

    mock_HO.side_effect = ho_side_effect

    # Mock query().filter_by().update()
    mock_query_result = MagicMock()
    mock_query.return_value.filter_by.return_value = mock_query_result

    # Act
    result = dummy_harvester.gather_stage(mock_harvest_job)

    # Assert expected harvest object IDs are returned
    assert sorted(result) == sorted(["ho-change", "ho-delete"])

    # Verify creation for change
    mock_HO.assert_any_call(
        guid=change_guid,
        job=mock_harvest_job,
        package_id="pkg-change",
        extras=[hoextra_change]
    )

    # Verify creation for delete
    mock_HO.assert_any_call(
        guid=delete_guid,
        job=mock_harvest_job,
        package_id="pkg-delete",
        extras=[hoextra_delete]
    )

    # Verify current=False set for delete
    mock_query_result.update.assert_called_once_with({"current": False}, False)


def test_fetch_stage_status_delete(dummy_harvester, harvest_object):
    harvest_object.extras = [HOExtra(key="status", value="delete")]
    result = dummy_harvester.fetch_stage(harvest_object)
    assert result is True

def test_fetch_stage_successful_fetch(configurable_harvester, harvest_object):
    harvester = configurable_harvester("<rdf>dummy content</rdf>")
    result = harvester.fetch_stage(harvest_object)

    assert result is True
    assert harvest_object.content == "<rdf>dummy content</rdf>"
    harvest_object.save.assert_called_once()

def test_fetch_stage_empty_record(configurable_harvester, harvest_object):
    harvester = configurable_harvester(None)
    harvester._save_object_error = MagicMock()
    harvest_object.extras = [HOExtra(key="status", value="change")]

    result = harvester.fetch_stage(harvest_object)

    assert result is False
    harvester._save_object_error.assert_called_once()
    assert "Empty record" in harvester._save_object_error.call_args[0][0]

def test_fetch_stage_save_exception(dummy_harvester, harvest_object):
    harvest_object.save.side_effect = Exception("cannot save")
    dummy_harvester._save_object_error = MagicMock()
    result = dummy_harvester.fetch_stage(harvest_object)

    assert result is False
    dummy_harvester._save_object_error.assert_called_once()
    assert "Error saving harvest object" in dummy_harvester._save_object_error.call_args[0][0]
