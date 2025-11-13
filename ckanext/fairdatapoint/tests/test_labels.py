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


class TestCollectValuesForField:
    """Test _collect_values_for_field function"""

    def test_collect_values_for_field_with_none(self):
        """Test _collect_values_for_field when value is None"""
        term_list = []
        result = _collect_values_for_field("theme", None, term_list)
        assert result == []
        assert result is term_list  # Should return the same list

    def test_collect_values_for_field_with_string(self):
        """Test _collect_values_for_field with a simple string value"""
        term_list = []
        result = _collect_values_for_field("theme", "http://example.com/theme", term_list)
        assert result == ["http://example.com/theme"]

    def test_collect_values_for_field_with_uriref(self):
        """Test _collect_values_for_field with a URIRef value"""
        term_list = []
        uri_ref = URIRef("http://example.com/theme")
        result = _collect_values_for_field("theme", uri_ref, term_list)
        assert result == ["http://example.com/theme"]

    def test_collect_values_for_field_with_list_of_strings(self):
        """Test _collect_values_for_field with a list of strings"""
        term_list = []
        result = _collect_values_for_field(
            "theme",
            ["http://example.com/theme1", "http://example.com/theme2"],
            term_list
        )
        assert result == ["http://example.com/theme1", "http://example.com/theme2"]

    def test_collect_values_for_field_with_list_of_urirefs(self):
        """Test _collect_values_for_field with a list of URIRefs"""
        term_list = []
        uri_refs = [URIRef("http://example.com/theme1"), URIRef("http://example.com/theme2")]
        result = _collect_values_for_field("theme", uri_refs, term_list)
        assert result == ["http://example.com/theme1", "http://example.com/theme2"]

    def test_collect_values_for_field_with_list_mixed_types(self):
        """Test _collect_values_for_field with a list containing strings and URIRefs"""
        term_list = []
        mixed_list = [
            "http://example.com/theme1",
            URIRef("http://example.com/theme2"),
            "http://example.com/theme3"
        ]
        result = _collect_values_for_field("theme", mixed_list, term_list)
        assert result == [
            "http://example.com/theme1",
            "http://example.com/theme2",
            "http://example.com/theme3"
        ]

    def test_collect_values_for_field_with_list_containing_dicts_nested_field(self):
        """Test _collect_values_for_field with a list containing dicts with nested fields"""
        term_list = []
        # qualified_relation has nested field "role" according to NESTED_FIELD_TRANSLATIONS
        value = [
            {
                "role": "http://example.com/role1",
                "other_field": "http://example.com/other"
            },
            {
                "role": "http://example.com/role2"
            }
        ]
        result = _collect_values_for_field("qualified_relation", value, term_list)
        # Should collect the nested "role" values, not "other_field"
        assert result == ["http://example.com/role1", "http://example.com/role2"]

    def test_collect_values_for_field_with_list_containing_dicts_no_nested_field(self):
        """Test _collect_values_for_field with a list containing dicts but field has no nested fields"""
        term_list = []
        # theme doesn't have nested fields in NESTED_FIELD_TRANSLATIONS
        value = [
            {
                "uri": "http://example.com/uri1",
                "name": "Theme 1"
            },
            {
                "uri": "http://example.com/uri2"
            }
        ]
        result = _collect_values_for_field("theme", value, term_list)
        # Should append the entire dict as-is (though this won't be a valid URI)
        # Actually, _append_value won't append dicts, so this will result in an empty list
        # Let me check the _append_value function - it only handles list, URIRef, and str
        assert result == []

    def test_collect_values_for_field_with_dict_nested_field(self):
        """Test _collect_values_for_field with a dict containing nested fields"""
        term_list = []
        # spatial_coverage has nested field "uri" according to NESTED_FIELD_TRANSLATIONS
        value = {
            "uri": "http://example.com/spatial",
            "name": "Some location"
        }
        result = _collect_values_for_field("spatial_coverage", value, term_list)
        # Should collect the nested "uri" value
        assert result == ["http://example.com/spatial"]

    def test_collect_values_for_field_with_dict_no_nested_field(self):
        """Test _collect_values_for_field with a dict but field has no nested fields"""
        term_list = []
        # theme doesn't have nested fields in NESTED_FIELD_TRANSLATIONS
        value = {
            "uri": "http://example.com/uri",
            "name": "Theme"
        }
        result = _collect_values_for_field("theme", value, term_list)
        # Should return term_list unchanged since theme has no nested fields
        assert result == []

    def test_collect_values_for_field_with_dict_nested_field_missing(self):
        """Test _collect_values_for_field with a dict that has nested field config but missing the nested key"""
        term_list = []
        # qualified_attribution has nested field "role" but it's missing
        value = {
            "other_field": "http://example.com/other"
        }
        result = _collect_values_for_field("qualified_attribution", value, term_list)
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

    def test_terms_in_package_dict_with_resource_access_service_empty_list(self):
        """Test terms_in_package_dict with resource where access_service is empty list"""
        package_dict = {
            "theme": "http://example.com/theme",
            "resources": [
                {
                    "name": "Resource 1",
                    "format": "http://example.com/format",
                    "access_services": []
                }
            ]
        }
        result = terms_in_package_dict(package_dict)
        expected_uris = {
            "http://example.com/theme",
            "http://example.com/format"
        }
        assert set(result) == expected_uris


class TestResolveLabelsEdgeCases:
    """Test resolve_labels edge cases"""

    @patch("ckanext.fairdatapoint.labels.get_list_unresolved_terms")
    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    @patch("ckan.plugins.toolkit.get_action")
    def test_resolve_labels_empty_filtered_translation_list(
        self,
        get_action,
        load_and_translate_uri,
        get_list_unresolved_terms,
    ):
        """Test resolve_labels when filtered_translation_list is empty (unsupported languages)"""
        get_list_unresolved_terms.return_value = [
            "http://www.wikidata.org/entity/Q29937289"
        ]
        # Translation list with only unsupported language codes (not in RESOLVE_LANGUAGES)
        translation_list = [
            {
                "term": "http://www.wikidata.org/entity/Q29937289",
                "term_translation": "Datenkatalog",
                "lang_code": "de",  # Not in RESOLVE_LANGUAGES ("en", "nl")
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
