# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import unittest
import ckanext.fairdatapoint.plugin as plugin
from unittest.mock import patch, MagicMock
from ckanext.fairdatapoint.harvesters import FairDataPointCivityHarvester
from ckanext.fairdatapoint.harvesters import fair_data_point_civity_harvester


class TestFairDataPointCivityHarvester(unittest.TestCase):

    def setUp(self):
        plugin.toolkit = MagicMock()

    def test_get_harvest_catalog_setting_from_dict(self):
        harvester = FairDataPointCivityHarvester()
        harvest_config_dict = {fair_data_point_civity_harvester.HARVEST_CATALOG: 'true'}
        result = harvester._get_harvest_catalog_setting(harvest_config_dict)
        self.assertTrue(result)

    @patch('ckan.plugins.toolkit.config')
    def test_get_harvest_catalog_setting_from_global_config(self, mock_config):
        mock_config.get.return_value = 'false'
        harvester = FairDataPointCivityHarvester()

        harvest_config_dict = {}
        result = harvester._get_harvest_catalog_setting(harvest_config_dict)

        self.assertFalse(result)
        mock_config.get.assert_called_once_with(fair_data_point_civity_harvester.HARVEST_CATALOG_CONFIG, False)

    @patch('ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_provider.FairDataPointRecordProvider'
           '.__init__')
    def test_setup_record_provider(self, mock_record_provider):
        mock_record_provider.return_value = None
        harvester = FairDataPointCivityHarvester()
        harvester._get_harvest_catalog_setting = MagicMock(return_value=True)
        harvest_url = 'http://example.com'
        harvest_config_dict = {fair_data_point_civity_harvester.HARVEST_CATALOG: 'true'}
        harvester.setup_record_provider(harvest_url, harvest_config_dict)
        harvester._get_harvest_catalog_setting.assert_called_once_with(harvest_config_dict)
        mock_record_provider.assert_called_once_with(harvest_url, True)

    @patch(
        'ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter'
        '.FairDataPointRecordToPackageConverter'
        '.__init__')
    def test_setup_record_to_package_converter_with_profile(self, mock_converter):
        mock_converter.return_value = None
        harvester = FairDataPointCivityHarvester()
        harvest_url = 'http://example.com'
        harvest_config_dict = {fair_data_point_civity_harvester.PROFILE: 'test_profile'}
        harvester.setup_record_to_package_converter(harvest_url, harvest_config_dict)
        mock_converter.assert_called_once_with('test_profile')

    def test_setup_record_to_package_converter_raises_exception(self):
        # Instantiate the harvester
        harvester = FairDataPointCivityHarvester()

        # Test data without PROFILE in the dictionary
        harvest_url = 'http://example.com'
        harvest_config_dict = {}  # No PROFILE key

        # Verify that an exception is raised when PROFILE is missing
        with self.assertRaises(Exception) as context:
            harvester.setup_record_to_package_converter(harvest_url, harvest_config_dict)

        # Check the exception message
        self.assertEqual(
            str(context.exception),
            "[profile] not found in harvester config JSON"
        )
