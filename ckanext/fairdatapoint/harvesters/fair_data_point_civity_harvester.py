# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester
from ckanext.fairdatapoint.harvesters.config import (
    get_harvester_int_setting,
    get_harvester_setting,
)
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_provider import (
    FairDataPointRecordProvider,
)
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter,
)

PROFILE = "profile"
HARVEST_CATALOG = "harvest_catalogs"
REQUEST_TIMEOUT = "request_timeout"
DEFAULT_REQUEST_TIMEOUT = 100

# HARVEST_CATALOG_CONFIG = "ckanext.fairdatapoint.harvest_catalogs"

log = logging.getLogger(__name__)


class FairDataPointCivityHarvester(CivityHarvester):
    def setup_record_provider(self, harvest_url, harvest_config_dict):
        # Harvest catalog config can be set on global CKAN level, but can be overriden by harvest config
        harvest_catalogs = get_harvester_setting(
            harvest_config_dict, HARVEST_CATALOG, False
        )
        request_timeout = get_harvester_int_setting(
            harvest_config_dict, REQUEST_TIMEOUT, DEFAULT_REQUEST_TIMEOUT
        )

        self.record_provider = FairDataPointRecordProvider(
            harvest_url,
            harvest_catalogs,
            request_timeout=request_timeout,
        )

    def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
        if PROFILE in harvest_config_dict:
            self.record_to_package_converter = FairDataPointRecordToPackageConverter(
                harvest_config_dict.get(PROFILE)
            )
        else:
            raise Exception("[{0}] not found in harvester config JSON".format(PROFILE))

    @staticmethod
    def info():
        return {
            "name": "fair_data_point_harvester",
            "title": "FAIR data point harvester",
            "description": "Harvester for end points implementing the FAIR data point protocol",
        }
