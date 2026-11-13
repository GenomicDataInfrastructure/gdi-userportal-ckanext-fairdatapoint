# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
import json
import logging

from ckan import model
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
from ckanext.fairdatapoint.harvesters.domain.fair_data_point import (
    REQUEST_TIMEOUT as FDP_REQUEST_TIMEOUT,
)
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_provider import (
    FairDataPointRecordProvider,
)
from ckanext.fairdatapoint.harvesters.domain.identifier import Identifier
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter,
)
from ckanext.fairdatapoint.harvesters.metadata_profile import resolve_fdp_profile
from ckanext.fairdatapoint.run_scope import start_run

PROFILE = "profile"
HARVEST_CATALOG = "harvest_catalogs"
REQUEST_TIMEOUT = "request_timeout"
DEFAULT_REQUEST_TIMEOUT = FDP_REQUEST_TIMEOUT
# Registered by ckanext-gdi-userportal; called by name so that this extension needs no import of it.
CONFORMANCE_ACTION = "gdi_metadata_profile_conformance"

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

    def import_stage(self, harvest_object):
        outcome = super().import_stage(harvest_object)
        if outcome is True:
            self._warn_when_not_conformant(harvest_object)
        return outcome

    def _warn_when_not_conformant(self, harvest_object):
        """
        Say in the harvest log which metadata profile the dataset just stored falls short of.

        The profile is the one the source selected (or the deployment's main one), and the
        answer is computed by the ``gdi_userportal`` extension when that is installed. It is
        information only: it never blocks the import and never fails it.
        """
        try:
            if (
                not harvest_object.package_id
                or self._get_object_extra(harvest_object, "status") == "delete"
                or Identifier(harvest_object.guid).get_id_type() != "dataset"
            ):
                return
            profile = self._resolve_profile(self._get_harvest_config(harvest_object.source.config)).name
            if not profile:  # a raw RDF chain names no profile to hold the dataset to
                return
            try:
                action = toolkit.get_action(CONFORMANCE_ACTION)
            except KeyError:  # the extension that computes conformance is not installed
                return
            result = action(
                {"ignore_auth": True, "user": self._get_user_name()}, {"id": harvest_object.package_id}
            )
            outcome = result["profiles"].get(profile)
            if outcome and not outcome["conformant"]:
                shortfall = ", ".join(item["property"] for item in outcome["missing"]) or outcome.get("reason")
                log.warning(
                    "Dataset %s (harvest object %s) does not conform to metadata profile '%s'"
                    " at access layer %s: %s",
                    harvest_object.package_id,
                    harvest_object.id,
                    profile,
                    result.get("access_layer") or "unknown",
                    shortfall,
                )
        except Exception as error:  # the dataset is already stored; this is only a notice
            # The import committed already. A failed query must not leave the shared session
            # needing a rollback, because the harvester updates its harvest object next.
            model.Session.rollback()
            log.warning(
                "Could not compute the conformance of the dataset of harvest object %s: %s",
                harvest_object.id,
                error,
            )

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
