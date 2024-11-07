# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from unittest.mock import patch

import pytest
import requests_mock
from rdflib import Graph
from rdflib.compare import to_isomorphic

from ckanext.fairdatapoint.resolver import resolvable_label_resolver

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


class TestGenericResolverClass:

    wikidata_data_catalog_path = Path(
        TEST_DATA_DIRECTORY, "wikidata_data_catalog_entry.ttl"
    )

    def test_graph_loader(self):
        resolver = resolvable_label_resolver()
        with open(self.wikidata_data_catalog_path) as file:
            # Turns out RDFlib doesn't use requests
            with requests_mock.Mocker() as mock:
                mock.get(
                    "http://www.wikidata.org/entity/Q29937289",
                    body=file,
                    headers={"content-type": "text/turtle"},
                )

                reference_graph = Graph().parse(self.wikidata_data_catalog_path)

                new_graph = resolver.load_graph(
                    "http://www.wikidata.org/entity/Q29937289"
                )

                assert to_isomorphic(reference_graph) == to_isomorphic(new_graph)

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

    def test_load_translate(self):
        resolver = resolvable_label_resolver()
        with open(self.wikidata_data_catalog_path) as file:
            with requests_mock.Mocker() as mock:
                mock.get(
                    "http://www.wikidata.org/entity/Q29937289",
                    body=file,
                    headers={"content-type": "text/turtle"},
                )

                ckan_translation_list = resolver.load_and_translate_uri(
                    "http://www.wikidata.org/entity/Q29937289"
                )

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
