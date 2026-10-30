# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
import json
import logging

from ckan.plugins import implements, toolkit

from ckanext.dcat.interfaces import IDCATRDFHarvester
from ckanext.dcat.metadata_profiles import (
    ORIGIN_RDF_PROFILE,
    MetadataProfileError,
    installed_rdf_profiles,
)
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
from ckanext.fairdatapoint.harvesters.metadata_profile import resolve_fdp_profile
from ckanext.fairdatapoint.run_scope import start_run

PROFILE = "profile"
HARVEST_CATALOG = "harvest_catalogs"
REQUEST_TIMEOUT = "request_timeout"
DEFAULT_REQUEST_TIMEOUT = 100

# HARVEST_CATALOG_CONFIG = "ckanext.fairdatapoint.harvest_catalogs"

log = logging.getLogger(__name__)


class FairDataPointCivityHarvester(CivityHarvester):
    # The dcat_rdf harvester resolves the labels of a whole source in its gather stage and only
    # tells plugins which harvest job that is through this interface.
    implements(IDCATRDFHarvester, inherit=True)

    def before_download(self, url, harvest_job):
        start_run(harvest_job.id)
        return url, []

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

    def validate_config(self, config):
        """Called when a harvest source is saved; any exception rejects the config with its message."""
        if not config:
            config_dict = {}
        else:
            try:
                config_dict = json.loads(config)
            except ValueError as error:
                raise ValueError("The configuration is not valid JSON: {0}".format(error))
            if not isinstance(config_dict, dict):
                raise ValueError("The configuration must be a JSON object")

        # Only the profile is validated here; the other keys keep being read leniently.
        resolve_fdp_profile(config_dict, toolkit.config, installed_rdf_profiles())

        return config

    def gather_stage(self, harvest_job):
        source = harvest_job.source
        try:
            resolved = self._resolve_profile(self._get_harvest_config(source.config))
        except MetadataProfileError as error:
            # No fallback to the main profile: it would change the shape of the data unnoticed. Fail
            # the job through a gather error: raising would stop ckanext-harvest's gather consumer.
            self._save_gather_error(
                "Harvest source {0} cannot be harvested: {1}".format(source.id, error),
                harvest_job,
            )
            return None

        log.info(
            "Harvest job %s of source %s uses %s",
            harvest_job.id,
            source.id,
            resolved.describe(),
        )

        return super().gather_stage(harvest_job)

    def setup_record_to_package_converter(self, harvest_url, harvest_config_dict):
        resolved = self._resolve_profile(harvest_config_dict)

        if resolved.origin == ORIGIN_RDF_PROFILE:
            # The raw RDF profile chain of the source, handed over as it was written.
            profile = harvest_config_dict.get(PROFILE)
        else:
            profile = resolved.rdf_profiles

        self.record_to_package_converter = FairDataPointRecordToPackageConverter(profile)

    @staticmethod
    def _resolve_profile(harvest_config_dict):
        return resolve_fdp_profile(harvest_config_dict, toolkit.config)

    @staticmethod
    def info():
        return {
            "name": "fair_data_point_harvester",
            "title": "FAIR data point harvester",
            "description": "Harvester for end points implementing the FAIR data point protocol",
        }
