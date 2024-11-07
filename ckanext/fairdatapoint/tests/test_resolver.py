# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path

import pytest
import requests_mock
from rdflib import Graph
from rdflib.compare import to_isomorphic

from ckanext.fairdatapoint.resolver import resolvable_label_resolver

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


class TestGenericResolverClass:

    def test_graph_loader(self):
        resolver = resolvable_label_resolver()
        with open(Path(TEST_DATA_DIRECTORY, "wikidata_data_catalog_entry.ttl")) as file:
            with requests_mock.Mocker() as mock:
                mock.get(
                    "http://www.wikidata.org/entity/Q29937289",
                    body=file,
                    headers={"content-type": "text/turtle"},
                )

                reference_graph = Graph().parse(
                    Path(TEST_DATA_DIRECTORY, "wikidata_data_catalog_entry.ttl")
                )

                new_graph = resolver.load_graph(
                    "http://www.wikidata.org/entity/Q29937289"
                )

                assert to_isomorphic(reference_graph) == to_isomorphic(new_graph)
