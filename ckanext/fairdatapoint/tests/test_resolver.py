# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from unittest.mock import patch

import pytest
import rdflib
import requests_mock
from rdflib import Graph
from rdflib.compare import to_isomorphic

from ckanext.fairdatapoint.resolver import (
    _is_absolute_uri,
    resolvable_label_resolver,
    terms_in_package_dict,
)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


class TestGenericResolverClass:

    wikidata_data_catalog_path = Path(
        TEST_DATA_DIRECTORY, "wikidata_data_catalog_entry.ttl"
    )

    def test_literal_dict_from_graph(self):
        resolver = resolvable_label_resolver()
        reference_graph = Graph().parse(self.wikidata_data_catalog_path)

        resolver.label_graph = reference_graph

        literal_dict = resolver.literal_dict_from_graph(
            "http://www.wikidata.org/entity/Q29937289"
        )

        reference_dict = {
            "en": "data catalog",
            "nl": "datacatalogus",
            "de": "Datenkatalog",
        }

        assert literal_dict == reference_dict

    @patch("ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_graph")
    def test_load_translate(self, load_graph):
        resolver = resolvable_label_resolver()
        # with open(self.wikidata_data_catalog_path) as file:
        load_graph.return_value = rdflib.Graph().parse(self.wikidata_data_catalog_path)
        resolver.label_graph = rdflib.Graph().parse(self.wikidata_data_catalog_path)
        ckan_translation_list = resolver.load_and_translate_uri(
            "http://www.wikidata.org/entity/Q29937289"
        )
        load_graph.assert_called_once_with("http://www.wikidata.org/entity/Q29937289")

        # Make sure order is correct, as graph traversion is random
        ckan_translation_list = sorted(
            ckan_translation_list, key=lambda x: x["lang_code"]
        )

        reference_translation_list = [
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

        assert ckan_translation_list == reference_translation_list


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
    reference_uri = {
        "https://creativecommons.org/publicdomain/zero/1.0/",
        "http://publications.europa.eu/resource/authority/data-theme/HEAL",
        "http://id.loc.gov/vocabulary/iso639-1/en",
        "http://id.loc.gov/vocabulary/iso639-1/nl",
    }

    assert set(terms_in_package_dict(reference_package_dict)) == reference_uri
