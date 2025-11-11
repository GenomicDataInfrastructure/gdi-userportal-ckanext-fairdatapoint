# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from unittest.mock import patch

import pytest
from rdflib import URIRef

from ckanext.fairdatapoint.labels import (
    _collect_values_for_field,
    _is_absolute_uri,
    get_list_unresolved_terms,
    resolve_labels,
    terms_in_package_dict,
)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


@pytest.mark.parametrize(
    ["uri", "resolvable"],
    [
        # Regular resolvable URI
        ("http://www.wikidata.org/entity/Q1568346", True),
        # HTTPS uri
        ("https://example.com/example#uri", True),
        # No path
        ("http://example.com", False),
        # Not a URI at all
        ("appelflap", False),
        # Wrong protocol
        ("ftp://ftp.mozilla.org/robots.txt", False),
        # Empty value
        (None, False),
        # Wrong type
        (12123, False),
    ],
)
def test_absolute_uri(uri, resolvable):
    assert _is_absolute_uri(uri) == resolvable


def test_terms_in_package_dict():
    reference_package_dict = {
        "access_rights": [
            "open_access",
            "https://creativecommons.org/publicdomain/zero/1.0/",
        ],
        "theme": "http://publications.europa.eu/resource/authority/data-theme/HEAL",
        "language": [
            "http://id.loc.gov/vocabulary/iso639-1/en",
            "http://id.loc.gov/vocabulary/iso639-1/nl",
        ],
        "has_version": "0.0.1",
    }
    reference_uris = {
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "http://publications.europa.eu/resource/authority/data-theme/HEAL",
        "http://id.loc.gov/vocabulary/iso639-1/en",
        "http://id.loc.gov/vocabulary/iso639-1/nl",
    }

    assert set(terms_in_package_dict(reference_package_dict)) == reference_uris


class TestTermUpdates:

    @patch("ckan.plugins.toolkit.get_action")
    def test_unresolved_URIs(self, get_action):
        known_data = [
            {
                "term": "http://example.com/uri1",
                "term_translation": "moo",
                "lang_code": "en",
            },
        ]

        get_action.return_value.return_value = known_data

        out_list = get_list_unresolved_terms(
            ["http://example.com/uri1", "http://example.com/uri2"]
        )

        get_action.return_value.assert_called_once()
        assert out_list == ["http://example.com/uri2"]


@patch("ckanext.fairdatapoint.labels.get_list_unresolved_terms")
@patch(
    "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
)
@patch("ckan.plugins.toolkit.get_action")
def test_resolve_label_happy_flow(
    get_action,
    load_and_translate_uri,
    get_list_unresolved_terms,
    terms_in_package_dict,
):
    # get_list_unresolved_terms.r
    get_list_unresolved_terms.return_value = [
        "http://www.wikidata.org/entity/Q29937289"
    ]
    translation_list = [
        {
            "term": "http://www.wikidata.org/entity/Q29937289",
            "term_translation": "Datenkatalog",
            "lang_code": "de",
        },
        {
            "term": "http://www.wikidata.org/entity/Q29937289",
            "term_translation": "data catalog",
            "lang_code": "en",
        },
        {
            "term": "http://www.wikidata.org/entity/Q29937289",
            "term_translation": "datacatalogus",
            "lang_code": "nl",
        },
    ]
    expected_filtered_translation_list = translation_list[1:]

    load_and_translate_uri.return_value = translation_list
    get_action.return_value.return_value = {"success": "3 updated succesfully"}

    assert resolve_labels({"theme": "http://www.wikidata.org/entity/Q29937289"}) == 3

    get_action.return_value.assert_called_once_with(
        {"ignore_auth": True, "defer_commit": True},
        {"data": expected_filtered_translation_list},
    )
        # Should return term_list unchanged since "role" is not in the dict
        assert result == []

    def test_collect_values_for_field_with_list_containing_dicts_nested_field_missing(self):
        """Test _collect_values_for_field with list of dicts where nested field is missing in some"""
        term_list = []
        value = [
            {
                "role": "http://example.com/role1"
            },
            {
                "other_field": "http://example.com/other"
            },
            {
                "role": "http://example.com/role2"
            }
        ]
        result = _collect_values_for_field("qualified_relation", value, term_list)
        # Should collect only the "role" values that exist
        assert result == ["http://example.com/role1", "http://example.com/role2"]


class TestTermsInPackageDictWithResources:
    """Test terms_in_package_dict with resources and access_services"""

    def test_terms_in_package_dict_with_resource_and_access_service(self):
        """Test terms_in_package_dict where package has a resource with an access_service"""
        package_dict = {
            "theme": "http://example.com/theme",
            "resources": [
                {
                    "name": "Resource 1",
                    "format": "http://example.com/format",
                    "access_services": [
                        {
                            "access_rights": "http://example.com/access_rights",
                            "language": "http://example.com/language",
                            "theme": "http://example.com/service_theme"
                        }
                    ]
                }
            ]
        }
        result = terms_in_package_dict(package_dict)
        expected_uris = {
            "http://example.com/theme",
            "http://example.com/format",
            "http://example.com/access_rights",
            "http://example.com/language",
            "http://example.com/service_theme"
        }
        assert set(result) == expected_uris

    def test_terms_in_package_dict_with_multiple_resources_and_access_services(self):
        """Test terms_in_package_dict with multiple resources, each with access_services"""
        package_dict = {
            "theme": "http://example.com/theme",
            "resources": [
                {
                    "name": "Resource 1",
                    "format": "http://example.com/format1",
                    "access_services": [
                        {
                            "access_rights": "http://example.com/access_rights1",
                            "language": "http://example.com/language1"
                        }
                    ]
                },
                {
                    "name": "Resource 2",
                    "format": "http://example.com/format2",
                    "access_services": [
                        {
                            "access_rights": "http://example.com/access_rights2",
                            "theme": "http://example.com/service_theme2"
                        },
                        {
                            "language": "http://example.com/language2"
                        }
                    ]
                }
            ]
        }
        result = terms_in_package_dict(package_dict)
        expected_uris = {
            "http://example.com/theme",
            "http://example.com/format1",
            "http://example.com/format2",
            "http://example.com/access_rights1",
            "http://example.com/access_rights2",
            "http://example.com/language1",
            "http://example.com/language2",
            "http://example.com/service_theme2"
        }
        assert set(result) == expected_uris

    def test_terms_in_package_dict_with_resource_no_access_service(self):
        """Test terms_in_package_dict with resource but no access_service"""
        package_dict = {
            "theme": "http://example.com/theme",
            "resources": [
                {
                    "name": "Resource 1",
                    "format": "http://example.com/format"
                }
            ]
        }
        result = terms_in_package_dict(package_dict)
        expected_uris = {
            "http://example.com/theme",
            "http://example.com/format"
        }
        assert set(result) == expected_uris
            },
            {
                "term": "http://www.wikidata.org/entity/Q29937289",
                "term_translation": "カタログ",
                "lang_code": "ja",  # Not in RESOLVE_LANGUAGES
            },
        ]

        load_and_translate_uri.return_value = translation_list

        result = resolve_labels({"theme": "http://www.wikidata.org/entity/Q29937289"})

        # Should return 0 when filtered_translation_list is empty
        assert result == 0
        # Should not call term_translation_update_many since filtered list is empty
        get_action.return_value.assert_not_called()
