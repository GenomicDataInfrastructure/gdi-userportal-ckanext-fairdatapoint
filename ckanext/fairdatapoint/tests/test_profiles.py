# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from pathlib import Path

import pytest
from rdflib import Graph, URIRef

from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter,
)
from ckanext.fairdatapoint.profiles import (
    FAIRDataPointDCATAPProfile,
    validate_tags,
)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


@pytest.mark.parametrize(
    "input_tags,expected_tags",
    [
        ([{"name": "CNS/Brain"}], [{"name": "CNS Brain"}]),
        (
            [{"name": "COVID-19"}, {"name": "3`-DNA"}],
            [{"name": "COVID-19"}, {"name": "3 -DNA"}],
        ),
        (
            [{"name": "something-1.1"}, {"name": "breast cancer"}],
            [{"name": "something-1.1"}, {"name": "breast cancer"}],
        ),
        ([{"name": "-"}], []),
        (
            [
                {
                    "name": "It is a ridiculously long (more 100 chars) text for a tag therefore it should be removed from the "
                    "result to prevent CKAN harvester from failing"
                }
            ],
            [],
        ),
        ([], []),
    ],
)
def test_validate_tags(input_tags, expected_tags):
    actual_tags = validate_tags(input_tags)
    assert actual_tags == expected_tags


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
def test_parse_dataset():
    """Dataset with keywords which should be modified"""
    fdp_record_to_package = FairDataPointRecordToPackageConverter(
        profile="fairdatapoint_dcat_ap"
    )
    data = (
        Graph().parse(Path(TEST_DATA_DIRECTORY, "dataset_cbioportal.ttl")).serialize()
    )
    actual = fdp_record_to_package.record_to_package(
        guid="catalog=https://health-ri.sandbox.semlab-leiden.nl/catalog/5c85cb9f-be4a-406c-ab0a-287fa787caa0;"
        "dataset=https://health-ri.sandbox.semlab-leiden.nl/dataset/d9956191-1aff-4181-ac8b-16b829135ed5",
        record=data,
        series_mapping=None,
    )
    extras_dict = {item["key"]: item["value"] for item in actual["extras"]}

    expected_resources = [
        {
            "name": "Clinical data for [PUBLIC] Low-Grade Gliomas (UCSF, Science 2014)",
            "description": "Clinical data for [PUBLIC] Low-Grade Gliomas (UCSF, Science 2014)",
            "access_url": "https://cbioportal.health-ri.nl/study/clinicalData?id=lgg_ucsf_2014",
            "license": "http://rdflicense.appspot.com/rdflicense/cc-by-nc-nd3.0",
            "url": "https://cbioportal.health-ri.nl/study/clinicalData?id=lgg_ucsf_2014",
            "uri": "https://health-ri.sandbox.semlab-leiden.nl/distribution/931ed9c4-ad23-47ff-b121-2eb428e57423",
            "distribution_ref": "https://health-ri.sandbox.semlab-leiden.nl/distribution/931ed9c4-ad23-47ff-b121-2eb428e57423",
        },
        {
            "name": "Mutations",
            "description": "Mutation data from whole exome sequencing of 23 grade II glioma tumor/normal pairs. (MAF)",
            "access_url": "https://cbioportal.health-ri.nl/study/summary?id=lgg_ucsf_2014",
            "license": "http://rdflicense.appspot.com/rdflicense/cc-by-nc-nd3.0",
            "url": "https://cbioportal.health-ri.nl/study/summary?id=lgg_ucsf_2014",
            "uri": "https://health-ri.sandbox.semlab-leiden.nl/distribution/ad00299f-6efb-42aa-823d-5ff2337f38f7",
            "distribution_ref": "https://health-ri.sandbox.semlab-leiden.nl/distribution/ad00299f-6efb-42aa-823d-5ff2337f38f7",
        },
    ]

    assert len(actual["resources"]) == len(expected_resources)
    for actual_resource, expected_resource in zip(
        actual["resources"], expected_resources
    ):
        assert actual_resource["retention_period"] == []
        for field, value in expected_resource.items():
            assert actual_resource[field] == value

    assert actual["title"] == "[PUBLIC] Low-Grade Gliomas (UCSF, Science 2014)"
    assert (
        actual["notes"]
        == "Whole exome sequencing of 23 grade II glioma tumor/normal pairs."
    )
    assert (
        actual["url"]
        == "https://cbioportal.health-ri.nl/study/summary?id=lgg_ucsf_2014"
    )
    assert actual["tags"] == [
        {"name": "CNS Brain"},
        {"name": "Diffuse Glioma"},
        {"name": "Glioma"},
    ]
    assert actual["license_id"] == ""
    assert actual["issued"] == "2019-10-30 23:00:00"
    assert actual["modified"] == "2019-10-30 23:00:00"
    assert actual["publisher"] == [
        {
            "email": "",
            "identifier": "",
            "name": "",
            "type": "",
            "uri": "https://www.health-ri.nl",
            "url": "",
        }
    ]
    assert actual["retention_period"] == []

    assert extras_dict["identifier"] == "lgg_ucsf_2014"
    assert json.loads(extras_dict["language"]) == [
        "http://id.loc.gov/vocabulary/iso639-1/en"
    ]
    assert json.loads(extras_dict["conforms_to"]) == [
        "https://health-ri.sandbox.semlab-leiden.nl/profile/2f08228e-1789-40f8-84cd-28e3288c3604"
    ]
    assert extras_dict["publisher_uri"] == "https://www.health-ri.nl"
    assert (
        extras_dict["uri"]
        == "https://health-ri.sandbox.semlab-leiden.nl/dataset/d9956191-1aff-4181-ac8b-16b829135ed5"
    )
    assert extras_dict["homepage"] == "http://localhost:5000"
    assert json.loads(extras_dict["is_referenced_by"]) == [
        "https://pubmed.ncbi.nlm.nih.gov/24336570"
    ]


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
class TestParseDatasetTagsTranslated:
    """Test parse_dataset with tags_translated as dict"""

    def test_parse_dataset_with_tags_translated_default_lang_exists(self):
        """Test parse_dataset when tags_translated has default_lang"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)
        profile._default_lang = "en"

        dataset_dict = {
            "tags_translated": {"en": ["tag1", "tag2"], "nl": ["tag1_nl", "tag2_nl"]}
        }
        dataset_ref = URIRef("http://example.com/dataset")

        result = profile.parse_dataset(dataset_dict, dataset_ref)

        # Verify tags_translated was sanitized
        assert "tags_translated" in result
        assert result["tags_translated"]["en"] == ["tag1", "tag2"]

        # Verify tags were set from default_lang
        assert result["tags"] == [{"name": "tag1"}, {"name": "tag2"}]

    def test_parse_dataset_with_tags_translated_default_lang_missing_uses_first_available(
        self,
    ):
        """Test parse_dataset when tags_translated doesn't have default_lang, uses first available"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)
        profile._default_lang = "en"

        dataset_dict = {
            "tags_translated": {"nl": ["tag1_nl", "tag2_nl"], "de": ["tag1_de"]}
        }
        dataset_ref = URIRef("http://example.com/dataset")

        result = profile.parse_dataset(dataset_dict, dataset_ref)

        # Verify tags were set from first available language (nl)
        assert result["tags"] == [{"name": "tag1_nl"}, {"name": "tag2_nl"}]

    def test_parse_dataset_with_tags_translated_empty_lists_skips_empty(self):
        """Test parse_dataset when tags_translated has empty lists, skips to first non-empty"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)
        profile._default_lang = "en"

        dataset_dict = {
            "tags_translated": {"en": [], "nl": [], "de": ["tag1_de", "tag2_de"]}
        }
        dataset_ref = URIRef("http://example.com/dataset")

        result = profile.parse_dataset(dataset_dict, dataset_ref)

        # Verify tags were set from first non-empty language (de)
        assert result["tags"] == [{"name": "tag1_de"}, {"name": "tag2_de"}]

    def test_parse_dataset_with_tags_translated_all_empty(self):
        """Test parse_dataset when all tags_translated lists are empty"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)
        profile._default_lang = "en"

        dataset_dict = {"tags_translated": {"en": [], "nl": []}}
        dataset_ref = URIRef("http://example.com/dataset")

        result = profile.parse_dataset(dataset_dict, dataset_ref)

        # Verify tags is empty list
        assert result["tags"] == []


class TestSanitizeTagsTranslated:
    """Test _sanitize_tags_translated method"""

    def test_sanitize_tags_translated_valid_tags(self):
        """Test _sanitize_tags_translated with valid tags"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)

        tags_translated = {
            "en": ["tag1", "tag2", "valid-tag"],
            "nl": ["tag1_nl", "tag2_nl"],
        }

        result = profile._sanitize_tags_translated(tags_translated)

        assert result["en"] == ["tag1", "tag2", "valid-tag"]
        assert result["nl"] == ["tag1_nl", "tag2_nl"]

    def test_sanitize_tags_translated_invalid_characters(self):
        """Test _sanitize_tags_translated with invalid characters"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)

        tags_translated = {
            "en": ["tag1/with", "tag2@invalid", "valid-tag"],
            "nl": ["tag1#nl"],
        }

        result = profile._sanitize_tags_translated(tags_translated)

        # Invalid characters should be replaced with spaces
        assert result["en"] == ["tag1 with", "tag2 invalid", "valid-tag"]
        assert result["nl"] == ["tag1 nl"]

    def test_sanitize_tags_translated_too_short(self):
        """Test _sanitize_tags_translated with tags that are too short"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)

        tags_translated = {"en": ["a", "tag", "valid-tag"]}

        result = profile._sanitize_tags_translated(tags_translated)

        # Tags shorter than 2 characters should be removed
        assert result["en"] == ["tag", "valid-tag"]

    def test_sanitize_tags_translated_too_long(self):
        """Test _sanitize_tags_translated with tags that are too long"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)

        long_tag = "a" * 101  # 101 characters
        tags_translated = {"en": [long_tag, "valid-tag"]}

        result = profile._sanitize_tags_translated(tags_translated)

        # Tags longer than 100 characters should be removed
        assert result["en"] == ["valid-tag"]

    def test_sanitize_tags_translated_empty_values(self):
        """Test _sanitize_tags_translated with empty values"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)

        tags_translated = {"en": ["tag1", "", "tag2", None], "nl": []}

        result = profile._sanitize_tags_translated(tags_translated)

        # Empty values should be filtered out
        assert result["en"] == ["tag1", "tag2"]
        assert result["nl"] == []

    def test_sanitize_tags_translated_mixed_valid_invalid(self):
        """Test _sanitize_tags_translated with mix of valid and invalid tags"""
        profile = FAIRDataPointDCATAPProfile(graph=Graph(), compatibility_mode=False)

        tags_translated = {
            "en": ["valid-tag", "a", "tag/with", "x" * 101, "another-valid"]
        }

        result = profile._sanitize_tags_translated(tags_translated)

        # Should keep only valid tags
        assert result["en"] == ["valid-tag", "tag with", "another-valid"]
