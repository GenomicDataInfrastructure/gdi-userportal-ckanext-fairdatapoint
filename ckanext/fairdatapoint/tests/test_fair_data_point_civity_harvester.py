# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import unittest
from unittest.mock import MagicMock, patch

from ckanext.dcat.metadata_profiles import MetadataProfileError
from ckanext.fairdatapoint.harvesters.config import (
    get_harvester_int_setting,
    get_harvester_setting,
)
import ckanext.fairdatapoint.plugin as plugin
from ckanext.fairdatapoint.harvesters import (
    FairDataPointCivityHarvester,
    fair_data_point_civity_harvester,
)


class TestFairDataPointCivityHarvester(unittest.TestCase):

    def setUp(self):
        plugin.toolkit = MagicMock()

    def test_get_harvest_catalog_setting_from_dict(self):
        harvest_config_dict = {fair_data_point_civity_harvester.HARVEST_CATALOG: "true"}
        result = get_harvester_setting(
            harvest_config_dict, fair_data_point_civity_harvester.HARVEST_CATALOG, False
        )
        self.assertTrue(result)

    @patch("ckan.plugins.toolkit.config")
    def test_get_harvest_catalog_setting_from_global_config(self, mock_config):
        mock_config.get.return_value = "false"
        harvest_config_dict = {}
        result = get_harvester_setting(
            harvest_config_dict, fair_data_point_civity_harvester.HARVEST_CATALOG, False
        )

        self.assertFalse(result)
        mock_config.get.assert_called_once_with(
            f"ckanext.fairdatapoint.{fair_data_point_civity_harvester.HARVEST_CATALOG}",
            False,
        )

    def test_get_request_timeout_setting_from_dict(self):
        harvest_config_dict = {
            fair_data_point_civity_harvester.REQUEST_TIMEOUT: "42"
        }
        result = get_harvester_int_setting(
            harvest_config_dict,
            fair_data_point_civity_harvester.REQUEST_TIMEOUT,
            fair_data_point_civity_harvester.DEFAULT_REQUEST_TIMEOUT,
        )
        self.assertEqual(result, 42)

    @patch("ckan.plugins.toolkit.config")
    def test_get_request_timeout_setting_from_global_config(self, mock_config):
        mock_config.get.return_value = "15"
        harvest_config_dict = {}
        result = get_harvester_int_setting(
            harvest_config_dict,
            fair_data_point_civity_harvester.REQUEST_TIMEOUT,
            fair_data_point_civity_harvester.DEFAULT_REQUEST_TIMEOUT,
        )

        self.assertEqual(result, 15)
        mock_config.get.assert_called_once_with(
            f"ckanext.fairdatapoint.{fair_data_point_civity_harvester.REQUEST_TIMEOUT}",
            fair_data_point_civity_harvester.DEFAULT_REQUEST_TIMEOUT,
        )

    @patch(
        "ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_provider.FairDataPointRecordProvider"
        ".__init__"
    )
    @patch(
        "ckanext.fairdatapoint.harvesters.fair_data_point_civity_harvester.get_harvester_int_setting"
    )
    @patch(
        "ckanext.fairdatapoint.harvesters.fair_data_point_civity_harvester.get_harvester_setting"
    )
    def test_setup_record_provider(
        self,
        get_harvester_setting,
        get_harvester_int_setting,
        mock_record_provider,
    ):
        mock_record_provider.return_value = None
        harvester = FairDataPointCivityHarvester()
        get_harvester_setting.return_value = True
        get_harvester_int_setting.return_value = 25
        harvest_url = "http://example.com"
        harvest_config_dict = {fair_data_point_civity_harvester.HARVEST_CATALOG: "true"}
        harvester.setup_record_provider(harvest_url, harvest_config_dict)
        get_harvester_setting.assert_called_once_with(
            harvest_config_dict, fair_data_point_civity_harvester.HARVEST_CATALOG, False
        )
        get_harvester_int_setting.assert_called_once_with(
            harvest_config_dict,
            fair_data_point_civity_harvester.REQUEST_TIMEOUT,
            fair_data_point_civity_harvester.DEFAULT_REQUEST_TIMEOUT,
        )
        mock_record_provider.assert_called_once_with(
            harvest_url, True, request_timeout=25
        )

    @patch(
        "ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter"
        ".FairDataPointRecordToPackageConverter"
        ".__init__"
    )
    def test_setup_record_to_package_converter_with_profile(self, mock_converter):
        mock_converter.return_value = None
        harvester = FairDataPointCivityHarvester()
        harvest_url = "http://example.com"
        harvest_config_dict = {fair_data_point_civity_harvester.PROFILE: "test_profile"}
        harvester.setup_record_to_package_converter(harvest_url, harvest_config_dict)
        mock_converter.assert_called_once_with("test_profile")

    @patch(
        "ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter"
        ".FairDataPointRecordToPackageConverter"
        ".__init__"
    )
    @patch.object(fair_data_point_civity_harvester, "toolkit")
    def test_setup_record_to_package_converter_without_profile_uses_main_profile(
        self, mock_toolkit, mock_converter
    ):
        # Without a profile key, the deployment's main metadata profile applies.
        mock_converter.return_value = None
        mock_toolkit.config = {
            "ckanext.dcat.metadata_profiles": "gdi_current",
            "ckanext.dcat.metadata_profiles.main": "gdi_current",
            "ckanext.dcat.metadata_profiles.gdi_current.rdf_profiles": "fairdatapoint_dcat_ap euro_dcat_ap_nl",
        }

        FairDataPointCivityHarvester().setup_record_to_package_converter(
            "http://example.com", {}
        )

        mock_converter.assert_called_once_with(
            ["fairdatapoint_dcat_ap", "euro_dcat_ap_nl"]
        )

    @patch.object(fair_data_point_civity_harvester, "toolkit")
    def test_setup_record_to_package_converter_without_any_profile_raises_exception(
        self, mock_toolkit
    ):
        # A deployment without metadata profiles or a default chain, and a source without a profile
        mock_toolkit.config = {}

        harvester = FairDataPointCivityHarvester()

        with self.assertRaisesRegex(
            MetadataProfileError, "No RDF profiles to parse with"
        ):
            harvester.setup_record_to_package_converter("http://example.com", {})
