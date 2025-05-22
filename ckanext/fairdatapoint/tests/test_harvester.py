# SPDX-FileCopyrightText: 2025 Health-RI
#
# SPDX-License-Identifier: Apache-2.0

import pytest
from unittest.mock import patch, MagicMock

from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester


@pytest.fixture
def mock_harvest_source():
    class MockSource:
        id = "civity-source-id"
        url = "http://dummy-url.com"
        config = None
        owner_org = "org-id"
    return MockSource()

@pytest.fixture
def mock_harvest_job():
    job = MagicMock()
    job.source.url = "http://test.com"
    job.source.config = None
    job.source.id = "source-id"
    return job

@pytest.fixture
def dummy_harvester():
    class DummyFDPHarvester(CivityHarvester):
        def setup_record_provider(self, harvest_url, harvest_config_dict):
            self.record_provider = MagicMock()

        def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
            pass  # Not needed for gather stage

    return DummyFDPHarvester()


@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HOExtra")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.HarvestObject")
@patch("ckanext.fairdatapoint.harvesters.civity_harvester.model.Session.query")
def test_gather_stage_creates_new_object(mock_query, mock_HO, mock_HOExtra, dummy_harvester, mock_harvest_job):
    dummy_harvester._get_guids_in_harvest = lambda job: {"new-guid"}
    dummy_harvester._get_guids_to_package_ids_from_database = lambda job: {}

    mock_query.return_value.filter_by.return_value.first.return_value = None
    mock_HOExtra.return_value = "Extra(status=new)"

    mock_obj = MagicMock(id="obj-new-guid")
    mock_HO.return_value = mock_obj

    result = dummy_harvester.gather_stage(mock_harvest_job)

    assert result == ["obj-new-guid"]
    mock_HOExtra.assert_called_once_with(key="status", value="new")
    mock_HO.assert_called_once()

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