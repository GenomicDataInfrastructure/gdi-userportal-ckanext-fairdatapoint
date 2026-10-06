# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from unittest.mock import patch

import pytest
from rdflib import URIRef

from ckanext.fairdatapoint import labels
from ckanext.fairdatapoint.labels import (
    _collect_values_for_field,
    _is_absolute_uri,
    get_list_unresolved_terms,
    get_missing_languages,
    resolve_labels,
    start_label_run,
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

    URI_EN_ONLY = "http://example.com/uri1"
    URI_UNKNOWN = "http://example.com/uri2"
    URI_COMPLETE = "http://example.com/uri3"

    KNOWN_DATA = [
        {"term": URI_EN_ONLY, "term_translation": "moo", "lang_code": "en"},
        {"term": "http://example.com/uri3", "term_translation": "cow", "lang_code": "en"},
        {"term": "http://example.com/uri3", "term_translation": "koe", "lang_code": "nl"},
    ]

    @patch("ckan.plugins.toolkit.get_action")
    def test_a_term_missing_one_language_is_unresolved(self, get_action):
        get_action.return_value.return_value = self.KNOWN_DATA

        out_list = get_list_unresolved_terms(
            [self.URI_EN_ONLY, self.URI_UNKNOWN, self.URI_COMPLETE]
        )

        get_action.return_value.assert_called_once()
        assert sorted(out_list) == sorted([self.URI_EN_ONLY, self.URI_UNKNOWN])

    @patch("ckan.plugins.toolkit.get_action")
    def test_missing_languages_are_reported_per_term(self, get_action):
        get_action.return_value.return_value = self.KNOWN_DATA

        missing = get_missing_languages(
            [self.URI_EN_ONLY, self.URI_UNKNOWN, self.URI_COMPLETE]
        )

        assert missing == {self.URI_EN_ONLY: {"nl"}, self.URI_UNKNOWN: {"en", "nl"}}

    @patch("ckan.plugins.toolkit.get_action")
    def test_only_the_requested_languages_count(self, get_action):
        get_action.return_value.return_value = self.KNOWN_DATA

        assert get_missing_languages([self.URI_EN_ONLY], languages=["en"]) == {}


@patch("ckanext.fairdatapoint.labels.get_missing_languages")
@patch(
    "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
)
@patch("ckan.plugins.toolkit.get_action")
def test_resolve_label_happy_flow(
    get_action,
    load_and_translate_uri,
    get_missing_languages,
):
    get_missing_languages.return_value = {
        "http://www.wikidata.org/entity/Q29937289": {"en", "nl"}
    }
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

    def test_terms_in_package_dict_with_publisher_and_creator(self):
        """Regression test: publisher_type/type nested inside publisher and creator
        must be collected. See NESTED_FIELD_TRANSLATIONS for "publisher"/"creator" -
        those nested rules only fire if "publisher"/"creator" are in PACKAGE_REPLACE_FIELDS."""
        package_dict = {
            "publisher": [
                {
                    "uri": "http://example.com/publisher-agent",
                    "name": "Example Publisher",
                    "publisher_type": [
                        "http://purl.org/adms/publishertype/Academia-ScientificOrganisation"
                    ],
                    "type": "http://example.com/publisher-type",
                }
            ],
            "creator": [
                {
                    "uri": "http://example.com/creator-agent",
                    "name": "Example Creator",
                    "publisher_type": ["http://example.com/creator-publisher-type"],
                    "type": "http://example.com/creator-type",
                }
            ],
        }
        result = terms_in_package_dict(package_dict)
        expected_uris = {
            "http://purl.org/adms/publishertype/Academia-ScientificOrganisation",
            "http://example.com/publisher-type",
            "http://example.com/creator-publisher-type",
            "http://example.com/creator-type",
        }
        assert set(result) == expected_uris

    def test_terms_in_package_dict_with_qualified_attribution_agent(self):
        """An agent of a qualified attribution is an agent like a publisher or a
        creator: its publisher_type, type and country(ies) are all collected."""
        package_dict = {
            "qualified_attribution": [
                {
                    "role": "http://example.com/role",
                    "agent": [
                        {
                            "name": "Example Agent",
                            "publisher_type": ["http://example.com/agent-publisher-type"],
                            "type": "http://example.com/agent-type",
                            "country": [
                                "http://publications.europa.eu/resource/authority/country/DEU",
                                "http://publications.europa.eu/resource/authority/country/FRA",
                            ],
                        }
                    ],
                }
            ]
        }
        result = terms_in_package_dict(package_dict)
        expected_uris = {
            "http://example.com/role",
            "http://example.com/agent-publisher-type",
            "http://example.com/agent-type",
            "http://publications.europa.eu/resource/authority/country/DEU",
            "http://publications.europa.eu/resource/authority/country/FRA",
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

    @patch("ckanext.fairdatapoint.labels.get_missing_languages")
    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    @patch("ckan.plugins.toolkit.get_action")
    def test_resolve_labels_empty_filtered_translation_list(
        self,
        get_action,
        load_and_translate_uri,
        get_missing_languages,
    ):
        """Test resolve_labels when filtered_translation_list is empty (unsupported languages)"""
        get_missing_languages.return_value = {
            "http://www.wikidata.org/entity/Q29937289": {"en", "nl"}
        }
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


class TestResolveLabelsMissingLanguages:
    """A term that is known in one language still gets its other languages resolved,
    without touching the translations that are already there."""

    TERM = "http://publications.europa.eu/resource/authority/country/DEU"
    FETCHED = [
        {"term": TERM, "term_translation": "Germany", "lang_code": "en"},
        {"term": TERM, "term_translation": "Duitsland", "lang_code": "nl"},
    ]

    @patch("ckanext.fairdatapoint.labels.get_missing_languages")
    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    @patch("ckan.plugins.toolkit.get_action")
    def test_only_the_missing_language_is_stored(
        self, get_action, load_and_translate_uri, get_missing_languages
    ):
        get_missing_languages.return_value = {self.TERM: {"nl"}}
        load_and_translate_uri.return_value = self.FETCHED
        get_action.return_value.return_value = {"success": "1 updated succesfully"}

        resolve_labels({"creator": [{"country": [self.TERM]}]})

        get_action.return_value.assert_called_once_with(
            {"ignore_auth": True, "defer_commit": True},
            {"data": [self.FETCHED[1]]},
        )

    @patch("ckanext.fairdatapoint.labels.get_missing_languages")
    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    @patch("ckan.plugins.toolkit.get_action")
    def test_nothing_is_stored_when_the_source_has_no_missing_language(
        self, get_action, load_and_translate_uri, get_missing_languages
    ):
        get_missing_languages.return_value = {self.TERM: {"nl"}}
        load_and_translate_uri.return_value = [self.FETCHED[0]]

        assert resolve_labels({"creator": [{"country": [self.TERM]}]}) == 0
        get_action.return_value.assert_not_called()

    @patch("ckanext.fairdatapoint.labels.get_missing_languages")
    def test_nothing_is_fetched_when_every_language_is_known(self, get_missing_languages):
        get_missing_languages.return_value = {}

        assert resolve_labels({"creator": [{"country": [self.TERM]}]}) == -1


class TestUnavailableLanguagesCache:
    """A language the source does not have is only asked for once per harvest run, and
    forgotten when that run is over."""

    TERM = "http://publications.europa.eu/resource/authority/country/DEU"
    ENGLISH_ONLY = [{"term": TERM, "term_translation": "Germany", "lang_code": "en"}]

    @pytest.fixture(autouse=True)
    def clean_cache(self):
        labels._unavailable_languages.clear()
        labels._current_run.set(None)
        labels._last_run_check = 0.0
        yield
        labels._unavailable_languages.clear()
        labels._current_run.set(None)

    @staticmethod
    def _resolve(term, missing, load_and_translate_uri):
        with patch(
            "ckanext.fairdatapoint.labels.get_missing_languages",
            return_value=missing,
        ), patch("ckan.plugins.toolkit.get_action"), patch.object(
            labels, "_forget_finished_runs"
        ):
            return resolve_labels({"theme": term})

    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    def test_a_language_the_source_lacks_is_asked_for_once_per_run(self, load):
        load.return_value = self.ENGLISH_ONLY
        start_label_run("job-1")

        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)
        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)
        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)

        assert load.call_count == 1

    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    def test_only_the_unavailable_language_is_skipped(self, load):
        load.return_value = self.ENGLISH_ONLY
        start_label_run("job-1")
        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)

        # another language of the same term is still asked for
        self._resolve(self.TERM, {self.TERM: {"nl", "en"}}, load)

        assert load.call_count == 2

    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    def test_nothing_is_cached_without_a_run(self, load):
        load.return_value = self.ENGLISH_ONLY

        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)
        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)

        assert load.call_count == 2
        assert labels._unavailable_languages == {}

    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    def test_a_run_does_not_use_what_another_run_found(self, load):
        load.return_value = self.ENGLISH_ONLY
        start_label_run("job-1")
        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)

        start_label_run("job-2")
        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)

        assert load.call_count == 2

    @patch(
        "ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_and_translate_uri"
    )
    def test_a_language_that_was_returned_is_not_remembered_as_unavailable(self, load):
        load.return_value = self.ENGLISH_ONLY + [
            {"term": self.TERM, "term_translation": "Duitsland", "lang_code": "nl"}
        ]
        start_label_run("job-1")

        self._resolve(self.TERM, {self.TERM: {"nl"}}, load)

        assert labels._unavailable_languages == {}

    @patch("ckan.model.Session")
    def test_runs_that_are_not_running_anymore_are_forgotten(self, session):
        labels._unavailable_languages.update(
            {"job-1": {self.TERM: {"nl"}}, "job-2": {self.TERM: {"nl"}}}
        )
        # only job-2 is still running
        session.query.return_value.filter.return_value.filter.return_value = [("job-2",)]

        labels._forget_finished_runs(force=True)

        assert list(labels._unavailable_languages) == ["job-2"]

    @patch("ckan.model.Session")
    def test_starting_a_run_forgets_finished_runs(self, session):
        labels._unavailable_languages["job-1"] = {self.TERM: {"nl"}}
        session.query.return_value.filter.return_value.filter.return_value = []

        start_label_run("job-2")

        assert labels._unavailable_languages == {}

    @patch("ckan.model.Session")
    def test_the_check_is_throttled(self, session):
        labels._unavailable_languages["job-1"] = {self.TERM: {"nl"}}
        session.query.return_value.filter.return_value.filter.return_value = []

        labels._forget_finished_runs()
        labels._unavailable_languages["job-1"] = {self.TERM: {"nl"}}
        labels._forget_finished_runs()

        assert session.query.call_count == 1
        assert "job-1" in labels._unavailable_languages

    @patch("ckan.model.Session")
    def test_the_cache_is_kept_when_the_database_cannot_be_asked(self, session):
        labels._unavailable_languages["job-1"] = {self.TERM: {"nl"}}
        session.query.side_effect = RuntimeError("database down")

        labels._forget_finished_runs(force=True)

        assert "job-1" in labels._unavailable_languages


def test_the_dcat_harvester_hands_over_its_harvest_job():
    from unittest.mock import MagicMock

    from ckanext.fairdatapoint.harvesters import FairDataPointCivityHarvester

    labels._current_run.set(None)
    job = MagicMock(id="job-42")

    url, errors = FairDataPointCivityHarvester().before_download("http://example.com", job)

    assert (url, errors) == ("http://example.com", [])
    assert labels._current_run.get() == "job-42"
    labels._current_run.set(None)
