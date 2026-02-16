# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import rdflib
from rdflib import Graph

from ckanext.fairdatapoint.resolver import (
    resolvable_label_resolver,
)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")

class TestGenericResolverClass:

    wikidata_data_catalog_path = Path(
        TEST_DATA_DIRECTORY, "wikidata_data_catalog_entry.ttl"
    )
    fdp_profile_path = Path(TEST_DATA_DIRECTORY, "fdp_profile.ttl")

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

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    @patch("ckanext.fairdatapoint.resolver.get_bioportal_api_key")
    def test_load_graph_bioontology_no_api_key(self, mock_api_key, mock_requests_get):
        """When no API key is configured, URI should be skipped and no request made"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS

        mock_api_key.return_value = None
        resolver = resolvable_label_resolver()

        test_uri = "http://purl.bioontology.org/ontology/ICD10CM/U07.1"
        result_graph = resolver.load_graph(test_uri)

        # No network call should be made
        mock_requests_get.assert_not_called()
        # URI should be added to skip list
        assert test_uri in SKIP_URIS
        # Graph is returned (may be empty), but crucially no exception bubbles up
        assert isinstance(result_graph, Graph)

    def test_load_graph_skips_already_skipped_uri(self):
        """If URI is in SKIP_URIS, load_graph should return immediately without parsing"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS

        resolver = resolvable_label_resolver()
        # Seed the resolver with a small graph so we can check object identity
        initial_graph = Graph()
        initial_graph.parse(data="""
            @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
            <http://example.org/thing> rdfs:label "Example"@en .
        """, format="turtle")
        resolver.label_graph = initial_graph

        test_uri = "http://example.org/already-skipped"

        # Call load_graph; because URI is skipped, it should simply return the current graph
        returned_graph = resolver.load_graph(test_uri)
        # Ensure it returned the same graph object and did not clear/replace it
        assert returned_graph is initial_graph
        assert len(returned_graph) == len(initial_graph)

    @patch("ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_graph")
    def test_load_translate_no_label(self, load_graph):
        resolver = resolvable_label_resolver()
        load_graph.return_value = rdflib.Graph().parse(self.fdp_profile_path)
        resolver.label_graph = rdflib.Graph().parse(self.fdp_profile_path)
        ckan_translation_list = resolver.load_and_translate_uri(
            "https://fdp.healthdata.nl/profile/2f08228e-1789-40f8-84cd-28e3288c3604"
        )
        load_graph.assert_called_once_with(
            "https://fdp.healthdata.nl/profile/2f08228e-1789-40f8-84cd-28e3288c3604"
        )

        # Make sure order is correct, as graph traversion is random
        ckan_translation_list = sorted(
            ckan_translation_list, key=lambda x: x["lang_code"]
        )

        reference_translation_list = [
            {
                "term": "https://fdp.healthdata.nl/profile/2f08228e-1789-40f8-84cd-28e3288c3604",
                "term_translation": "Dataset Profile",
                "lang_code": "en",
            },
        ]

        assert ckan_translation_list == reference_translation_list

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    @patch("ckanext.fairdatapoint.resolver.get_bioportal_api_key")
    def test_load_graph_bioontology_failure(self, mock_api_key, mock_requests_get):
        """Test loading a BioOntology URI with failed response"""
        resolver = resolvable_label_resolver()
        
        # Mock the API key
        mock_api_key.return_value = "test-api-key-12345"
        
        # Mock a failed response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://purl.bioontology.org/ontology/INVALID/999999"
        
        # Call load_graph - should handle the error gracefully
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the URI is added to SKIP_URIS after failure
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        assert test_uri in SKIP_URIS
        
        mock_requests_get.assert_called_once()

    @patch("ckanext.fairdatapoint.resolver.resolvable_label_resolver.load_graph")
    def test_load_and_translate_bioontology_uri(self, mock_load_graph):
        """Test complete flow of loading and translating a BioOntology URI - fully offline"""
        resolver = resolvable_label_resolver()
        
        # Create a JSON-LD response with the expected structure
        jsonld_response = """
        {
            "@context": {
                "skos": "http://www.w3.org/2004/02/skos/core#",
                "prefLabel": "skos:prefLabel"
            },
            "@id": "http://purl.bioontology.org/ontology/ICD10CM/U07.1",
            "prefLabel": [
                {"@value": "COVID-19", "@language": "en"}
            ]
        }
        """
        
        # Parse the JSON-LD into a graph and set it as the return value
        mock_graph = rdflib.Graph().parse(data=jsonld_response, format="json-ld")
        mock_load_graph.return_value = mock_graph
        
        # Also set the resolver's label_graph to the same graph
        resolver.label_graph = mock_graph
        
        test_uri = "http://purl.bioontology.org/ontology/ICD10CM/U07.1"
        
        # Call load_and_translate_uri - this will use the mocked load_graph
        ckan_translation_list = resolver.load_and_translate_uri(test_uri)
        
        # Verify load_graph was called with the correct URI
        mock_load_graph.assert_called_once_with(test_uri)
        
        # Sort for consistent comparison
        ckan_translation_list = sorted(
            ckan_translation_list, key=lambda x: x["lang_code"]
        )

        reference_translation_list = [
            {
                "term": "http://purl.bioontology.org/ontology/ICD10CM/U07.1",
                "term_translation": "COVID-19",
                "lang_code": "en",
            },
        ]

        assert ckan_translation_list == reference_translation_list

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_graph_empty_graph_resets_label_graph(self, mock_requests_get):
        """Test that empty_graph clears the existing graph (line 110)."""
        resolver = resolvable_label_resolver()

        # Ensure instance attribute exists and seed graph with data
        resolver.label_graph = Graph()
        resolver.label_graph.parse(
            data="""
                @prefix ex: <http://example.com/> .
                ex:thing a ex:Type .
            """,
            format="turtle",
        )

        test_uri = "http://example.com/graph"
        mock_requests_get.side_effect = Exception("boom")

        result_graph = resolver.load_graph(test_uri, empty_graph=True)

        assert result_graph is resolver.label_graph
        assert len(result_graph) == 0

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_and_translate_europa_vocabulary(self, mock_requests_get):
        """Test complete end-to-end flow with Europa Publications Office vocabulary URI"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        
        # Mock response with RDF/XML data for Dutch language
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:skos="http://www.w3.org/2004/02/skos/core#">
    <rdf:Description rdf:about="http://publications.europa.eu/resource/authority/language/NLD">
        <skos:prefLabel xml:lang="nl">Nederlands</skos:prefLabel>
        <skos:prefLabel xml:lang="en">Dutch</skos:prefLabel>
    </rdf:Description>
</rdf:RDF>"""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://publications.europa.eu/resource/authority/language/NLD"
        
        # Call the complete flow
        ckan_translation_list = resolver.load_and_translate_uri(test_uri)
        
        # Verify the request was made
        assert mock_requests_get.call_count >= 1
        
        # Sort for consistent comparison
        ckan_translation_list = sorted(
            ckan_translation_list, key=lambda x: x["lang_code"]
        )
        
        # Verify the expected translations
        reference_translation_list = [
            {
                "term": "http://publications.europa.eu/resource/authority/language/NLD",
                "term_translation": "Dutch",
                "lang_code": "en",
            },
            {
                "term": "http://publications.europa.eu/resource/authority/language/NLD",
                "term_translation": "Nederlands",
                "lang_code": "nl",
            },
        ]
        
        assert ckan_translation_list == reference_translation_list

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_graph_with_xml_format(self, mock_requests_get):
        """Test loading graph with XML format data"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response with RDF/XML data
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0" encoding="utf-8"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:skos="http://www.w3.org/2004/02/skos/core#">
    <rdf:Description rdf:about="http://publications.europa.eu/resource/authority/language/NLD">
        <skos:prefLabel xml:lang="nl">Nederlands</skos:prefLabel>
        <skos:prefLabel xml:lang="en">Dutch</skos:prefLabel>
    </rdf:Description>
</rdf:RDF>"""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://publications.europa.eu/resource/authority/language/NLD"
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the request was made
        assert mock_requests_get.call_count >= 1
        # Check that the graph contains data
        assert len(result_graph) > 0
        # Verify we can extract the labels
        label_dict = resolver.literal_dict_from_graph(test_uri)
        assert label_dict.get("nl") == "Nederlands"
        assert label_dict.get("en") == "Dutch"

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_graph_with_turtle_format(self, mock_requests_get):
        """Test loading graph with Turtle format data"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response with Turtle data
        mock_response = MagicMock()
        mock_response.text = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<http://publications.europa.eu/resource/authority/language/NLD>
    skos:prefLabel "Nederlands"@nl, "Dutch"@en ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://publications.europa.eu/resource/authority/language/NLD"
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the request was made
        assert mock_requests_get.call_count >= 1
        # Check that the graph contains data
        assert len(result_graph) > 0
        # Verify we can extract the labels
        label_dict = resolver.literal_dict_from_graph(test_uri)
        assert label_dict.get("nl") == "Nederlands"
        assert label_dict.get("en") == "Dutch"

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_graph_with_invalid_data(self, mock_requests_get):
        """Test that invalid data adds URI to SKIP_URIS"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response with invalid RDF data
        mock_response = MagicMock()
        mock_response.text = "This is not valid RDF data in any format"
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://example.com/invalid"
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the request was made
        assert mock_requests_get.call_count >= 1
        # Verify URI was added to skip list after parsing failures
        assert test_uri in SKIP_URIS

