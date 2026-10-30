# SPDX-FileCopyrightText: 2026 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
"""
A harvest source selecting its metadata profile in its config JSON.

Pure tests: no CKAN database, no plugins. The deployment config is a dict handed to the
harvester in place of ``toolkit.config``, and the dataset schema is handed to the RDF
profiles through ``base.get_action``, like the dcat health profile tests do.
"""
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest
from ckanext.dcat.metadata_profiles import MetadataProfileError
from ckanext.dcat.profiles import base

from ckanext.fairdatapoint.harvesters import fair_data_point_civity_harvester as harvester_module
from ckanext.fairdatapoint.harvesters.civity_harvester import CivityHarvester
from ckanext.fairdatapoint.harvesters.fair_data_point_civity_harvester import (
    FairDataPointCivityHarvester,
)
from ckanext.fairdatapoint.harvesters.metadata_profile import resolve_fdp_profile

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")
RECORD = Path(TEST_DATA_DIRECTORY, "metadata_profile_dataset.ttl").read_text()
GUID = "dataset=https://fdp.example.org/dataset/profile-selection"

GDI_CHAIN = "fairdatapoint_dcat_ap euro_dcat_ap_nl"
R8_CHAIN = "euro_health_dcat_ap_r8"
INSTALLED = {"fairdatapoint_dcat_ap", "fairdatapoint_additive", "euro_dcat_ap_nl", "euro_health_dcat_ap_r8"}


def _field(name, **extra):
    return {"field_name": name, "label": name, **extra}


# The fields of the superset dataset type that the fixture touches.
SCHEMA = {
    "scheming_version": 2,
    "dataset_type": "dataset",
    "form_languages": ["en", "nl"],
    "dataset_fields": [
        _field("identifier"),
        _field("alternative_title", preset="multiple_text", validators="ignore_missing scheming_multiple_text"),
        _field("has_structured_data", preset="select", validators="ignore_missing boolean_validator"),
        _field(
            "hdab",
            repeating_subfields=[
                _field(n)
                for n in ("uri", "name", "name_translated", "email", "url", "type", "publisher_note", "telephone")
            ],
        ),
    ],
    "resource_fields": [],
}


def deployment(enabled, main="gdi_current"):
    """The CKAN config the profile generator writes for the enabled metadata profiles."""
    chains = {"gdi_current": GDI_CHAIN, "healthdcat_r8": R8_CHAIN}
    config = {
        "ckanext.dcat.metadata_profiles": " ".join(enabled),
        "ckanext.dcat.metadata_profiles.main": main,
        "ckanext.dcat.rdf.profiles": chains[main],
    }
    for name in chains:
        # The ini keeps the chain of a profile that was enabled in an earlier start.
        config[f"ckanext.dcat.metadata_profiles.{name}.rdf_profiles"] = chains[name]
    return config


BOTH = deployment(["healthdcat_r8", "gdi_current"])
ONLY_GDI = deployment(["gdi_current"])
R8_IS_MAIN = deployment(["healthdcat_r8", "gdi_current"], main="healthdcat_r8")


@pytest.fixture
def run():
    """Parse the fixture record the way a harvest job does, for a source config and a deployment."""
    labels = mock.MagicMock()

    def parse(source_config, config=BOTH):
        harvester = FairDataPointCivityHarvester()
        with mock.patch.object(harvester_module, "toolkit", SimpleNamespace(config=config)), \
                mock.patch.object(base, "get_action", lambda name: lambda ctx, data: SCHEMA), \
                mock.patch("ckanext.fairdatapoint.profiles.resolve_labels", labels):
            harvester.setup_record_to_package_converter("https://fdp.example.org", source_config)
            return harvester.record_to_package_converter.record_to_package(GUID, RECORD)

    parse.labels = labels
    return parse


class TestSourceWithoutAProfile:
    def test_gets_the_main_profile(self, run):
        dataset = run({})

        assert dataset["title"] == "Profile selection dataset"
        assert "alternative_title" not in dataset
        assert "has_structured_data" not in dataset
        # gdi_current does not read the R8 cv:contactPoint
        assert dataset["hdab"][0]["email"] == ""
        assert "telephone" not in dataset["hdab"][0]

    def test_null_and_empty_values_count_as_absent(self, run):
        expected = run({})

        assert run({"metadata_profile": None}) == expected
        assert run({"metadata_profile": ""}) == expected

    def test_reads_exactly_what_the_legacy_default_chain_read_before(self, run):
        # Today's sources carry "profile": "<chain>". The main profile must not change what they get.
        assert run({}) == run({"profile": GDI_CHAIN})

    def test_follows_a_deployment_whose_main_profile_is_r8(self, run):
        dataset = run({}, config=R8_IS_MAIN)

        assert dataset["has_structured_data"] is True

    def test_the_fair_data_point_clean_up_runs(self, run):
        dataset = run({})

        assert [tag["name"] for tag in dataset["tags"]] == ["CNS Brain", "COVID-19"]
        run.labels.assert_called_once()


class TestGdiCurrent:
    def test_selected_explicitly_it_equals_the_default(self, run):
        assert run({"metadata_profile": "gdi_current"}) == run({})

    def test_a_source_can_pick_it_while_r8_is_the_main_profile(self, run):
        dataset = run({"metadata_profile": "gdi_current"}, config=R8_IS_MAIN)

        assert "has_structured_data" not in dataset
        assert dataset["hdab"][0]["email"] == ""

    def test_the_chain_is_the_one_in_the_pack_without_anything_added(self):
        resolved = resolve_fdp_profile({"metadata_profile": "gdi_current"}, BOTH)

        assert resolved.rdf_profiles == GDI_CHAIN.split()


class TestHealthDcatR8:
    def test_reads_the_r8_properties(self, run):
        dataset = run({"metadata_profile": "healthdcat_r8"})

        assert dataset["alternative_title"] == ["Another title"]
        assert dataset["has_structured_data"] is True
        assert dataset["hdab"][0]["email"] == "hdab@example.org"
        assert dataset["hdab"][0]["url"] == "https://example.org/contact"
        assert dataset["hdab"][0]["telephone"] == "+31 20 555 0100"

    def test_keeps_the_fair_data_point_clean_up(self, run):
        dataset = run({"metadata_profile": "healthdcat_r8"})

        assert [tag["name"] for tag in dataset["tags"]] == ["CNS Brain", "COVID-19"]
        run.labels.assert_called_once()

    def test_the_fair_data_point_behaviour_is_added_after_the_r8_chain(self):
        resolved = resolve_fdp_profile({"metadata_profile": "healthdcat_r8"}, BOTH)

        assert resolved.rdf_profiles == ["euro_health_dcat_ap_r8", "fairdatapoint_additive"]

    def test_differs_from_the_main_profile_only_where_the_profiles_differ(self, run):
        r8 = run({"metadata_profile": "healthdcat_r8"})
        gdi = run({})

        assert r8["title"] == gdi["title"]
        assert r8["tags"] == gdi["tags"]
        assert r8["identifier"] == gdi["identifier"]
        assert r8 != gdi

    def test_the_same_source_reads_alike_when_the_deployment_only_enables_r8(self, run):
        config = deployment(["healthdcat_r8"], main="healthdcat_r8")

        assert run({}, config=config) == run({"metadata_profile": "healthdcat_r8"})


class TestLegacyProfileKey:
    def test_is_handed_to_the_converter_as_written(self):
        harvester = FairDataPointCivityHarvester()
        with mock.patch.object(harvester_module, "toolkit", SimpleNamespace(config=BOTH)), \
                mock.patch.object(harvester_module, "FairDataPointRecordToPackageConverter") as converter:
            harvester.setup_record_to_package_converter("https://fdp.example.org", {"profile": "fairdatapoint_dcat_ap"})

        converter.assert_called_once_with("fairdatapoint_dcat_ap")

    def test_gets_no_fair_data_point_profile_added(self):
        resolved = resolve_fdp_profile({"profile": "euro_health_dcat_ap_r8"}, BOTH)

        assert resolved.rdf_profiles == ["euro_health_dcat_ap_r8"]

    def test_still_applies_on_a_deployment_that_does_not_enable_that_profile(self, run):
        dataset = run({"profile": R8_CHAIN}, config=ONLY_GDI)

        assert dataset["has_structured_data"] is True
        # a raw chain is a raw chain: no clean-up is added behind the user's back
        assert [tag["name"] for tag in dataset["tags"]] == ["CNS/Brain", "COVID-19"]


class TestChainComposition:
    def test_an_fdp_profile_in_the_chain_is_not_doubled(self):
        config = {**BOTH, "ckanext.dcat.metadata_profiles.healthdcat_r8.rdf_profiles": "euro_health_dcat_ap_r8 fairdatapoint_additive"}

        assert resolve_fdp_profile({"metadata_profile": "healthdcat_r8"}, config).rdf_profiles == [
            "euro_health_dcat_ap_r8",
            "fairdatapoint_additive",
        ]

    def test_a_deployment_without_any_chain_is_an_error_not_the_parser_default(self):
        with pytest.raises(MetadataProfileError, match="No RDF profiles to parse with"):
            resolve_fdp_profile({}, {})

    def test_a_deployment_without_metadata_profiles_uses_its_rdf_profiles_option(self):
        config = {"ckanext.dcat.rdf.profiles": "euro_health_dcat_ap fairdatapoint_dcat_ap"}

        resolved = resolve_fdp_profile({}, config)

        assert resolved.rdf_profiles == ["euro_health_dcat_ap", "fairdatapoint_dcat_ap"]


class TestValidateConfig:
    @pytest.fixture
    def validate(self):
        def validate(config, deployment_config=BOTH):
            with mock.patch.object(harvester_module, "toolkit", SimpleNamespace(config=deployment_config)), \
                    mock.patch.object(harvester_module, "installed_rdf_profiles", return_value=INSTALLED):
                return FairDataPointCivityHarvester().validate_config(config)

        return validate

    @pytest.mark.parametrize("config", [None, "", "{}", '{"metadata_profile": ""}', '{"metadata_profile": null}'])
    def test_accepts_a_config_without_a_profile(self, validate, config):
        assert validate(config) == config

    @pytest.mark.parametrize("name", ["gdi_current", "healthdcat_r8"])
    def test_accepts_an_enabled_profile_and_returns_the_config_unchanged(self, validate, name):
        config = json.dumps({"metadata_profile": name, "request_timeout": 25})

        assert validate(config) == config

    def test_accepts_a_legacy_profile_chain(self, validate):
        config = json.dumps({"profile": GDI_CHAIN})

        assert validate(config) == config

    def test_rejects_a_profile_that_is_not_enabled_and_names_the_enabled_ones(self, validate):
        with pytest.raises(MetadataProfileError) as error:
            validate('{"metadata_profile": "healthdcat_r8"}', deployment_config=ONLY_GDI)

        assert str(error.value) == (
            "Metadata profile 'healthdcat_r8' is not enabled on this deployment. Enabled: gdi_current"
        )

    def test_rejects_an_unknown_profile(self, validate):
        with pytest.raises(MetadataProfileError, match="'healthdcat_r9' is not enabled.*Enabled: healthdcat_r8, gdi_current"):
            validate('{"metadata_profile": "healthdcat_r9"}')

    @pytest.mark.parametrize("value", ["5", "true", '["gdi_current"]', '{"a": 1}'])
    def test_rejects_a_value_that_is_not_a_string(self, validate, value):
        with pytest.raises(MetadataProfileError, match="'metadata_profile' must be a string"):
            validate('{"metadata_profile": %s}' % value)

    def test_rejects_both_keys(self, validate):
        with pytest.raises(MetadataProfileError, match="Both 'metadata_profile' and 'profile' are set"):
            validate(json.dumps({"metadata_profile": "gdi_current", "profile": GDI_CHAIN}))

    def test_rejects_a_legacy_profile_that_is_not_installed(self, validate):
        with pytest.raises(MetadataProfileError, match="not installed: euro_dcat_ap_9"):
            validate('{"profile": "fairdatapoint_dcat_ap euro_dcat_ap_9"}')

    @pytest.mark.parametrize("config", ["{not json", '["metadata_profile"]', '"gdi_current"'])
    def test_rejects_a_config_that_is_not_a_json_object(self, validate, config):
        with pytest.raises(ValueError, match="JSON"):
            validate(config)


class TestHarvestJob:
    @staticmethod
    def job(source_config):
        source = SimpleNamespace(id="source-1", url="https://fdp.example.org", config=json.dumps(source_config))
        return SimpleNamespace(id="job-1", source=source)

    def gather(self, source_config, config=BOTH):
        harvester = FairDataPointCivityHarvester()
        harvester._save_gather_error = mock.MagicMock()
        with mock.patch.object(harvester_module, "toolkit", SimpleNamespace(config=config)), \
                mock.patch.object(CivityHarvester, "gather_stage", return_value=["object-1"]) as gather:
            result = harvester.gather_stage(self.job(source_config))
        return harvester, gather, result

    def test_logs_the_effective_profile_for_a_source_without_one(self, caplog):
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            _, gather, result = self.gather({})

        assert result == ["object-1"]
        gather.assert_called_once()
        assert (
            "Harvest job job-1 of source source-1 uses metadata profile 'gdi_current', "
            "RDF profiles: fairdatapoint_dcat_ap euro_dcat_ap_nl, from: default"
        ) in caplog.messages

    def test_logs_the_profile_a_source_selected(self, caplog):
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            self.gather({"metadata_profile": "healthdcat_r8"})

        assert (
            "Harvest job job-1 of source source-1 uses metadata profile 'healthdcat_r8', "
            "RDF profiles: euro_health_dcat_ap_r8 fairdatapoint_additive, from: metadata_profile"
        ) in caplog.messages

    def test_logs_a_legacy_chain_as_such(self, caplog):
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            self.gather({"profile": "fairdatapoint_dcat_ap"})

        assert (
            "Harvest job job-1 of source source-1 uses no named metadata profile, "
            "RDF profiles: fairdatapoint_dcat_ap, from: profile"
        ) in caplog.messages

    def test_a_profile_retired_since_the_source_was_saved_fails_the_job_without_a_fallback(self):
        harvester = FairDataPointCivityHarvester()
        harvester._save_gather_error = mock.MagicMock()

        with mock.patch.object(harvester_module, "toolkit", SimpleNamespace(config=ONLY_GDI)), \
                mock.patch.object(CivityHarvester, "gather_stage") as gather:
            # Not an exception: the gather consumer of ckanext-harvest would stop on one.
            result = harvester.gather_stage(self.job({"metadata_profile": "healthdcat_r8"}))

        assert result is None
        gather.assert_not_called()
        (message, job), _ = harvester._save_gather_error.call_args
        assert "source-1" in message
        assert "Metadata profile 'healthdcat_r8' is not enabled on this deployment. Enabled: gdi_current" in message
        assert job.id == "job-1"


class TestConformanceWarning:
    """The harvest log names the profile a stored dataset falls short of; it never changes the import."""

    SHORT = {
        "access_layer": "NON_PUBLIC",
        "profiles": {
            "gdi_current": {"conformant": True, "mandatory": 0, "missing": []},
            "healthdcat_r8": {
                "conformant": False,
                "mandatory": 14,
                "missing": [{"property": "health data access body", "fields": ["hdab"]}, {"property": "keyword", "fields": ["tags"]}],
            },
        },
    }

    @staticmethod
    def harvest_object(source_config=None, guid=GUID, status="new", package_id="pkg-1"):
        return SimpleNamespace(
            id="object-1",
            package_id=package_id,
            guid=guid,
            source=SimpleNamespace(id="source-1", url="https://fdp.example.org", config=json.dumps(source_config or {})),
            extras=[SimpleNamespace(key="status", value=status)],
        )

    def import_(self, harvest_object, action_result=None, super_result=True, config=BOTH, get_action=None):
        harvester = FairDataPointCivityHarvester()
        harvester._get_user_name = lambda: "site-user"
        action = mock.MagicMock(return_value=action_result or self.SHORT)
        get_action = get_action or mock.MagicMock(return_value=action)
        with mock.patch.object(harvester_module, "toolkit", SimpleNamespace(config=config, get_action=get_action)), \
                mock.patch.object(CivityHarvester, "import_stage", return_value=super_result):
            result = harvester.import_stage(harvest_object)
        return result, action, get_action

    def warnings(self, caplog):
        return [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]

    def test_names_the_profile_the_layer_and_what_is_missing(self, caplog):
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            result, action, get_action = self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}))

        assert result is True
        get_action.assert_called_once_with("gdi_metadata_profile_conformance")
        action.assert_called_once_with({"ignore_auth": True, "user": "site-user"}, {"id": "pkg-1"})
        assert self.warnings(caplog) == [
            "Dataset pkg-1 (harvest object object-1) does not conform to metadata profile 'healthdcat_r8'"
            " at access layer NON_PUBLIC: health data access body, keyword"
        ]

    def test_holds_a_source_without_a_profile_to_the_main_profile(self, caplog):
        # gdi_current has no mandatory properties, so only a main profile with rules can fall short
        no_layer = {
            "access_layer": None,
            "profiles": {"healthdcat_r8": {"conformant": False, "mandatory": 0, "missing": [], "reason": "access rights is missing"}},
        }
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            self.import_(self.harvest_object(), action_result=no_layer, config=R8_IS_MAIN)

        assert self.warnings(caplog) == [
            "Dataset pkg-1 (harvest object object-1) does not conform to metadata profile 'healthdcat_r8'"
            " at access layer unknown: access rights is missing"
        ]

    def test_a_source_held_to_gdi_current_never_warns(self, caplog):
        satisfied = {"access_layer": None, "profiles": {"gdi_current": {"conformant": True, "mandatory": 0, "missing": []}}}
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            self.import_(self.harvest_object(), action_result=satisfied)

        assert self.warnings(caplog) == []

    def test_holds_the_dataset_only_to_the_profile_of_its_source(self, caplog):
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            self.import_(self.harvest_object({"metadata_profile": "gdi_current"}))  # r8 fails, gdi_current does not

        assert self.warnings(caplog) == []

    def test_a_conforming_dataset_logs_nothing(self, caplog):
        fine = {"access_layer": "PUBLIC", "profiles": {"healthdcat_r8": {"conformant": True, "mandatory": 10, "missing": []}}}
        with caplog.at_level(logging.DEBUG, logger=harvester_module.log.name):
            self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}), action_result=fine)

        assert caplog.records == []

    def test_a_raw_rdf_chain_names_no_profile_to_check(self):
        _, action, get_action = self.import_(self.harvest_object({"profile": "fairdatapoint_dcat_ap"}))

        get_action.assert_not_called()
        action.assert_not_called()

    @pytest.mark.parametrize("super_result", [False, "unchanged"])
    def test_only_a_stored_dataset_is_checked(self, super_result):
        result, action, _ = self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}), super_result=super_result)

        assert result == super_result
        action.assert_not_called()

    def test_a_deleted_dataset_is_not_checked(self):
        _, action, _ = self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}, status="delete"))

        action.assert_not_called()

    def test_a_series_is_not_checked(self):
        _, action, _ = self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}, guid="dataseries=https://fdp.example.org/series/1"))

        action.assert_not_called()

    def test_a_deployment_without_the_conformance_action_imports_quietly(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=harvester_module.log.name):
            result, _, _ = self.import_(
                self.harvest_object({"metadata_profile": "healthdcat_r8"}), get_action=mock.MagicMock(side_effect=KeyError("gdi_metadata_profile_conformance"))
            )

        assert result is True
        assert caplog.records == []

    def test_a_failing_check_never_fails_the_import(self, caplog):
        broken = mock.MagicMock(return_value=mock.MagicMock(side_effect=RuntimeError("boom")))
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name), \
                mock.patch.object(harvester_module, "model") as model:
            result, _, _ = self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}), get_action=broken)

        assert result is True
        # a database error inside the check must not leave the shared session needing a rollback
        model.Session.rollback.assert_called_once_with()
        assert self.warnings(caplog) == ["Could not compute the conformance of the dataset of harvest object object-1: boom"]

    def test_a_source_whose_profile_was_retired_still_imports_what_the_base_stored(self, caplog):
        with caplog.at_level(logging.INFO, logger=harvester_module.log.name):
            result, action, _ = self.import_(self.harvest_object({"metadata_profile": "healthdcat_r8"}), config=ONLY_GDI)

        assert result is True
        action.assert_not_called()
        assert len(self.warnings(caplog)) == 1 and "Could not compute" in self.warnings(caplog)[0]
