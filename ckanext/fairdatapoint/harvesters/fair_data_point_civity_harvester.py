# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_provider import (
    FairDataPointRecordProvider,
)
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter,
)
from ckan.plugins import toolkit

PROFILE = "profile"
HARVEST_CATALOG = "harvest_catalogs"
HARVEST_CATALOG_CONFIG = "ckanext.fairdatapoint.harvest_catalogs"

log = logging.getLogger(__name__)


class FairDataPointCivityHarvester(CivityHarvester):

    def setup_record_provider(self, harvest_url, harvest_config_dict):
        # Harvest catalog config can be set on global CKAN level, but can be overriden by harvest config
        harvest_catalogs = toolkit.asbool(
            toolkit.config.get(HARVEST_CATALOG_CONFIG, False)
        )
        if HARVEST_CATALOG in harvest_config_dict:
            harvest_catalogs = toolkit.asbool(
                harvest_config_dict.get(HARVEST_CATALOG, False)
            )
            log.debug("harvest_catalogs from harvester config: %s", harvest_catalogs)
        else:
            log.debug("harvest_catalogs from ckan config: %s", harvest_catalogs)

        self.record_provider = FairDataPointRecordProvider(
            harvest_url, harvest_catalogs
        )

    def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
        if PROFILE in harvest_config_dict:
            self.record_to_package_converter = FairDataPointRecordToPackageConverter(
                harvest_config_dict.get(PROFILE)
            )
        else:
            raise Exception("[{0}] not found in harvester config JSON".format(PROFILE))

    def info(self):
        return {
            "name": "fair_data_point_harvester",
            "title": "FAIR data point harvester",
            "description": "Harvester for end points implementing the FAIR data point protocol",
        }
