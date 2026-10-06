# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import rdflib
from rdflib import Graph

from ckanext.fairdatapoint import resolver as resolver_module
from ckanext.fairdatapoint.resolver import (
    MAX_REDIRECTS,
    UnsafeUriError,
    resolvable_label_resolver,
    _canonicalize_dpv_uri,
    _canonicalize_uri,
    _check_public_destination,
    _get_public,


    _canonicalize_wikidata_uri,
)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")
PUBLIC_ADDRESS = "93.184.216.34"


@pytest.fixture(autouse=True)
def public_dns():
    """Every host resolves to a public address, so the tests do not depend on DNS"""
    with patch(
        "ckanext.fairdatapoint.resolver._resolve_addresses",
        return_value={PUBLIC_ADDRESS},
    ):
        yield


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


class TestWikidataURIHandling:
    """Test Wikidata-specific URI handling in the resolver"""

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_wikidata_uri_with_non_entity_or_wiki_path_is_skipped(
        self, mock_requests_get
    ):
        """Wikidata-domain URI with other paths should be skipped without raising."""
        from ckanext.fairdatapoint.resolver import SKIP_URIS

        SKIP_URIS.clear()

        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()

        test_uri = "https://www.wikidata.org/some/other/path"

        # Execute: this must not raise
        result_graph = resolver.load_graph(test_uri)

        # The resolver currently skips unsupported Wikidata paths
        assert test_uri in SKIP_URIS
        # No outbound request is made because entity id extraction fails early
        mock_requests_get.assert_not_called()
        # Return type remains stable
        assert isinstance(result_graph, Graph)

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_wikidata_graph_with_entity_uri(self, mock_requests_get):
        """Test loading Wikidata graph with /entity/ format URI"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response with Turtle data
        mock_response = MagicMock()
        mock_response.text = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<http://www.wikidata.org/entity/Q123>
    rdfs:label "test entity"@en ;
    skos:prefLabel "test entiteit"@nl ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://www.wikidata.org/entity/Q123"
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the correct Wikidata API endpoint was called
        mock_requests_get.assert_called_once()
        called_url = mock_requests_get.call_args[0][0]
        called_kwargs = mock_requests_get.call_args[1]
        headers = called_kwargs.get("headers") or {}

        assert "Special:EntityData/Q123" in called_url

        # Verify that appropriate headers are sent for content negotiation and identification
        # (these assertions intentionally check for key substrings rather than exact matches,
        # to avoid over-coupling tests to minor header formatting changes)
        accept_header = headers.get("Accept", "")
        user_agent_header = headers.get("User-Agent", "")

        assert "turtle" in accept_header.lower()
        assert user_agent_header != ""

        # Check that the graph contains data
        assert len(result_graph) > 0

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_wikidata_graph_with_wiki_uri(self, mock_requests_get):
        """Test loading Wikidata graph with /wiki/ format URI"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response with Turtle data
        mock_response = MagicMock()
        mock_response.text = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://www.wikidata.org/entity/Q456>
    rdfs:label "another entity"@en ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        # Test with /wiki/ format (should be converted to Special:EntityData)
        test_uri = "http://www.wikidata.org/wiki/Q456"
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the correct Wikidata API endpoint was called
        mock_requests_get.assert_called_once()
        called_url = mock_requests_get.call_args[0][0]
        assert "Special:EntityData/Q456" in called_url
        
        # Check that the graph contains data
        assert len(result_graph) > 0

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_wikidata_graph_with_property_uri(self, mock_requests_get):
        """Test loading Wikidata graph with Property ID (P prefix)"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

<http://www.wikidata.org/entity/P31>
    rdfs:label "instance of"@en ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://www.wikidata.org/wiki/P31"
        result_graph = resolver.load_graph(test_uri)
        
        # Verify the correct endpoint with Property ID
        mock_requests_get.assert_called_once()
        called_url = mock_requests_get.call_args[0][0]
        assert "Special:EntityData/P31" in called_url

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_wikidata_graph_handles_http_error(self, mock_requests_get):
        """Test that HTTP errors are handled gracefully for Wikidata URIs"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock failed response
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 404")
        mock_requests_get.return_value = mock_response
        
        test_uri = "http://www.wikidata.org/entity/Q99999999"
        result_graph = resolver.load_graph(test_uri)
        
        # URI should be added to skip list after failure
        assert test_uri in SKIP_URIS
        # Should return the (empty) graph without raising exception
        assert isinstance(result_graph, Graph)

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_wikidata_different_domains(self, mock_requests_get):
        """Test that both wikidata.org and www.wikidata.org are recognized"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        mock_response = MagicMock()
        mock_response.text = """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
<http://www.wikidata.org/entity/Q789> rdfs:label "test"@en ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        # Test without www prefix
        test_uri1 = "http://wikidata.org/wiki/Q789"
        resolver.load_graph(test_uri1)
        
        assert mock_requests_get.call_count == 1
        called_url = mock_requests_get.call_args[0][0]
        assert "Special:EntityData/Q789" in called_url
        
        # Reset and test with www prefix
        mock_requests_get.reset_mock()
        SKIP_URIS.clear()
        resolver.label_graph = Graph()
        
        test_uri2 = "https://www.wikidata.org/entity/Q789"
        resolver.load_graph(test_uri2)
        
        assert mock_requests_get.call_count == 1
        called_url = mock_requests_get.call_args[0][0]
        assert "Special:EntityData/Q789" in called_url

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_and_translate_wikidata_uri_complete_flow(self, mock_requests_get):
        """Test complete end-to-end flow of loading and translating a Wikidata URI"""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()
        
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph()
        
        # Mock response with multilingual labels
        mock_response = MagicMock()
        mock_response.text = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<http://www.wikidata.org/entity/Q29937289>
    skos:prefLabel "data catalog"@en, "datacatalogus"@nl ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response
        
        # Use /entity/ format to match what Wikidata actually returns in the RDF
        test_uri = "http://www.wikidata.org/entity/Q29937289"
        
        # Call the complete flow
        ckan_translation_list = resolver.load_and_translate_uri(test_uri)
        
        # Verify translations were extracted
        assert len(ckan_translation_list) == 2
        
        # Sort for consistent comparison
        ckan_translation_list = sorted(
            ckan_translation_list, key=lambda x: x["lang_code"]
        )
        
        # Verify the expected format
        expected = [
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

        assert ckan_translation_list == expected


class TestDpvCanonicalization:
    """Tests for the DPV doc-page -> w3id.org URI canonicalizer and its wiring
    into `load_graph`/`literal_dict_from_graph`/`load_and_translate_uri`."""

    def test_canonicalize_core_module(self):
        assert _canonicalize_dpv_uri(
            "https://w3c.github.io/dpv/2.1/dpv/#ResearchAndDevelopment"
        ) == "https://w3id.org/dpv#ResearchAndDevelopment"

    def test_canonicalize_current_github_org(self):
        assert _canonicalize_dpv_uri(
            "https://w3c-cg.github.io/dpv/2.1/dpv/#AcademicResearch"
        ) == "https://w3id.org/dpv#AcademicResearch"

    def test_canonicalize_submodule(self):
        assert _canonicalize_dpv_uri(
            "https://w3c-cg.github.io/dpv/2.1/pd/#Age"
        ) == "https://w3id.org/dpv/pd#Age"

    def test_canonicalize_no_fragment(self):
        assert _canonicalize_dpv_uri(
            "https://w3c-cg.github.io/dpv/2.1/dpv/"
        ) == "https://w3id.org/dpv"

    def test_canonicalize_ignores_unrelated_host(self):
        assert _canonicalize_dpv_uri(
            "https://example.com/dpv/2.1/dpv/#ResearchAndDevelopment"
        ) is None

    def test_canonicalize_ignores_direct_file_links(self):
        """A path deeper than /dpv/<version>/<module>/ (e.g. a direct .ttl download)
        already works via content negotiation and should not be rewritten."""
        assert _canonicalize_dpv_uri(
            "https://w3c-cg.github.io/dpv/2.1/dpv/dpv.ttl"
        ) is None

    def test_canonicalize_host_is_case_insensitive(self):
        """URI hostnames are case-insensitive; an upper-cased GitHub Pages host
        should still be recognized and rewritten."""
        assert _canonicalize_dpv_uri(
            "https://W3C-CG.GITHUB.IO/dpv/2.1/dpv/#ResearchAndDevelopment"
        ) == "https://w3id.org/dpv#ResearchAndDevelopment"

    def test_canonicalize_uri_wrapper_swallows_malformed_input(self):
        """A malformed URI (e.g. an invalid IPv6-style host) makes urlparse raise
        ValueError inside an individual canonicalizer; `_canonicalize_uri` -- the
        function every caller actually uses -- treats that as "no match" rather
        than letting the exception escape."""
        malformed_uri = "http://[invalid"
        assert _canonicalize_uri(malformed_uri) == malformed_uri

    def test_load_graph_does_not_raise_on_malformed_uri(self):
        resolver = resolvable_label_resolver()
        result_graph = resolver.load_graph("http://[invalid")
        assert isinstance(result_graph, Graph)

    def test_literal_dict_from_graph_does_not_raise_on_malformed_uri(self):
        resolver = resolvable_label_resolver()
        assert resolver.literal_dict_from_graph("http://[invalid") == {}

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_graph_fetches_canonical_uri(self, mock_requests_get):
        """load_graph should fetch the w3id.org URI, not the doc-page URI."""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()

        resolver = resolvable_label_resolver()

        mock_response = MagicMock()
        mock_response.text = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<https://w3id.org/dpv#ResearchAndDevelopment>
    skos:prefLabel "Research and Development"@en ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response

        doc_page_uri = "https://w3c.github.io/dpv/2.1/dpv/#ResearchAndDevelopment"
        resolver.load_graph(doc_page_uri)

        fetched_uri = mock_requests_get.call_args.args[0]
        assert fetched_uri == "https://w3id.org/dpv#ResearchAndDevelopment"

    def test_literal_dict_from_graph_looks_up_canonical_subject(self):
        """literal_dict_from_graph should find labels even when the graph only
        contains the canonical w3id.org subject, given the original doc-page URI."""
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph().parse(
            data="""
                @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
                <https://w3id.org/dpv#ResearchAndDevelopment>
                    skos:prefLabel "Research and Development"@en .
            """,
            format="turtle",
        )

        literal_dict = resolver.literal_dict_from_graph(
            "https://w3c.github.io/dpv/2.1/dpv/#ResearchAndDevelopment"
        )

        assert literal_dict == {"en": "Research and Development"}

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_load_and_translate_dpv_doc_page_uri(self, mock_requests_get):
        """End-to-end: the stored translation is keyed by the original doc-page
        URI (matching what a harvested dataset actually references), even though
        the lookup happens against the canonical w3id.org URI."""
        from ckanext.fairdatapoint.resolver import SKIP_URIS
        SKIP_URIS.clear()

        resolver = resolvable_label_resolver()

        mock_response = MagicMock()
        mock_response.text = """@prefix skos: <http://www.w3.org/2004/02/skos/core#> .

<https://w3id.org/dpv#ResearchAndDevelopment>
    skos:prefLabel "Research and Development"@en ."""
        mock_response.raise_for_status = MagicMock()
        mock_requests_get.return_value = mock_response

        doc_page_uri = "https://w3c.github.io/dpv/2.1/dpv/#ResearchAndDevelopment"
        ckan_translation_list = resolver.load_and_translate_uri(doc_page_uri)

        assert ckan_translation_list == [
            {
                "term": doc_page_uri,
                "term_translation": "Research and Development",
                "lang_code": "en",
            }
        ]


def _resolving_to(*addresses):
    return patch(
        "ckanext.fairdatapoint.resolver._resolve_addresses",
        return_value=set(addresses),
    )


def _response(status_code=200, location=None):
    response = MagicMock(status_code=status_code)
    response.headers = {"Location": location} if location else {}
    return response


def _requests(*responses):
    return patch(
        "ckanext.fairdatapoint.resolver.requests.get", side_effect=list(responses)
    )


class TestPublicDestinations:
    """The URIs of harvested records are only requested when they go to a public address."""

    @pytest.mark.parametrize(
        "address",
        [
            "127.0.0.1",
            "10.0.0.5",
            "172.16.0.1",
            "192.168.1.10",
            "169.254.169.254",
            "100.64.0.1",
            "0.0.0.0",
            "224.0.0.1",
            "::1",
            "fe80::1",
            "fd00::1",
            "ff02::1",
            "::ffff:10.0.0.1",
            "::ffff:127.0.0.1",
        ],
    )
    def test_non_public_addresses_are_rejected(self, address):
        with _resolving_to(address), pytest.raises(UnsafeUriError):
            _check_public_destination("http://vocabulary.example/term")

    @pytest.mark.parametrize(
        "address", [PUBLIC_ADDRESS, "8.8.8.8", "2606:4700:4700::1111", "::ffff:8.8.8.8"]
    )
    def test_public_addresses_are_accepted(self, address):
        with _resolving_to(address):
            _check_public_destination("https://vocabulary.example/term")

    def test_a_host_with_one_non_public_address_is_rejected(self):
        with _resolving_to(PUBLIC_ADDRESS, "10.0.0.5"), pytest.raises(UnsafeUriError):
            _check_public_destination("http://vocabulary.example/term")

    @pytest.mark.parametrize(
        "url",
        [
            "file:///etc/passwd",
            "ftp://vocabulary.example/term",
            "gopher://vocabulary.example/",
            "http:///no-host",
            "//vocabulary.example/term",
        ],
    )
    def test_other_schemes_and_missing_hosts_are_rejected(self, url):
        with pytest.raises(UnsafeUriError):
            _check_public_destination(url)

    def test_a_host_that_cannot_be_resolved_is_rejected(self):
        with patch(
            "ckanext.fairdatapoint.resolver._resolve_addresses",
            side_effect=OSError("no such host"),
        ), pytest.raises(UnsafeUriError):
            _check_public_destination("http://vocabulary.example/term")

    def test_an_empty_answer_is_rejected(self):
        with _resolving_to(), pytest.raises(UnsafeUriError):
            _check_public_destination("http://vocabulary.example/term")


class TestPublicRedirects:
    """A redirect is checked like the request that led to it."""

    def test_a_response_that_is_not_a_redirect_is_returned(self):
        ok = _response(200)

        with _requests(ok) as mock_get:
            assert _get_public("http://vocabulary.example/term", {}) is ok

        # redirects are followed here, not by requests, so that each one is checked
        assert mock_get.call_args.kwargs["allow_redirects"] is False

    def test_a_redirect_to_a_public_host_is_followed(self):
        ok = _response(200)

        with _requests(_response(302, "http://other.example/term"), ok) as mock_get:
            assert _get_public("http://vocabulary.example/term", {}) is ok

        assert [call.args[0] for call in mock_get.call_args_list] == [
            "http://vocabulary.example/term",
            "http://other.example/term",
        ]

    def test_a_relative_redirect_is_resolved_against_the_url(self):
        with _requests(_response(301, "/other/term"), _response(200)) as mock_get:
            _get_public("https://vocabulary.example/term", {})

        assert mock_get.call_args_list[1].args[0] == "https://vocabulary.example/other/term"

    def test_a_redirect_to_a_non_public_address_is_not_followed(self):
        def resolve(hostname, port):
            return {"169.254.169.254"} if hostname == "metadata.internal" else {PUBLIC_ADDRESS}

        with patch(
            "ckanext.fairdatapoint.resolver._resolve_addresses", side_effect=resolve
        ), _requests(_response(302, "http://metadata.internal/latest")) as mock_get:
            with pytest.raises(UnsafeUriError):
                _get_public("http://vocabulary.example/term", {})

        assert mock_get.call_count == 1

    def test_too_many_redirects_are_rejected(self):
        loop = [_response(302, "http://vocabulary.example/next")] * (MAX_REDIRECTS + 1)

        with _requests(*loop) as mock_get, pytest.raises(UnsafeUriError):
            _get_public("http://vocabulary.example/term", {})

        assert mock_get.call_count == MAX_REDIRECTS + 1


class TestGenericLoaderDestinations:
    """The generic loader does not reach internal services."""

    def test_a_private_address_is_not_requested(self):
        resolver = resolvable_label_resolver()

        with _resolving_to("10.0.0.5"), patch(
            "ckanext.fairdatapoint.resolver.requests.get"
        ) as mock_get:
            assert resolver._load_generic_graph("http://internal.example/term") is False

        mock_get.assert_not_called()

    def test_load_graph_gives_no_labels_and_skips_the_uri(self):
        uri = "http://internal.example/term"
        resolver = resolvable_label_resolver()
        resolver_module.SKIP_URIS.discard(uri)

        try:
            with _resolving_to("10.0.0.5"), patch(
                "ckanext.fairdatapoint.resolver.requests.get"
            ) as mock_get:
                graph = resolver.load_graph(uri)

            mock_get.assert_not_called()
            assert len(graph) == 0
            assert uri in resolver_module.SKIP_URIS
        finally:
            resolver_module.SKIP_URIS.discard(uri)


class TestIcd10Resolver:
    """ICD-10 URIs are links into the WHO browser; labels come from its public JSON."""

    SUBCATEGORY = "http://icd.who.int/browse10/2019/en#/Y59.0"
    CATEGORY = "http://icd.who.int/browse10/2019/en#/Y59"

    @pytest.fixture(autouse=True)
    def _fresh_skip_uris(self, monkeypatch):
        from ckanext.fairdatapoint import resolver

        monkeypatch.setattr(resolver, "SKIP_URIS", set())

    @staticmethod
    def _response(json_data=None, text=""):
        response = MagicMock()
        response.json.return_value = json_data
        response.text = text
        return response

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_subcategory_label_comes_from_its_category_children(self, mock_get):
        mock_get.return_value = self._response(
            [
                {"ID": "Y59.0", "label": "Y59.0 Viral vaccines"},
                {"ID": "Y59.1", "label": "Y59.1 Rickettsial vaccines"},
            ]
        )

        result = resolvable_label_resolver().load_and_translate_uri(self.SUBCATEGORY)

        assert result == [
            {
                "term": self.SUBCATEGORY,
                "term_translation": "Viral vaccines",
                "lang_code": "en",
            }
        ]
        mock_get.assert_called_once()
        assert mock_get.call_args[0][0].endswith("/2019/en/JsonGetChildrenConcepts")
        assert mock_get.call_args[1]["params"]["ConceptId"] == "Y59"

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_category_label_comes_from_the_narrowest_block(self, mock_get):
        page = "Chapter XX (V01-Y98) Complications (Y40-Y84) Drugs (Y40-Y59) Y59"
        mock_get.side_effect = [
            self._response(text=page),
            self._response(
                [
                    {"ID": "Y58", "label": "Y58 Bacterial vaccines"},
                    {"ID": "Y59", "label": "Y59 Other and unspecified vaccines"},
                ]
            ),
        ]

        result = resolvable_label_resolver().load_and_translate_uri(self.CATEGORY)

        assert [r["term_translation"] for r in result] == [
            "Other and unspecified vaccines"
        ]
        assert mock_get.call_args_list[0][0][0].endswith("/GetConcept")
        assert mock_get.call_args_list[1][1]["params"]["ConceptId"] == "Y40-Y59"

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_label_uses_the_language_of_the_uri(self, mock_get):
        mock_get.return_value = self._response(
            [{"ID": "Y59.0", "label": "Y59.0 Virale vaccins"}]
        )
        uri = "http://icd.who.int/browse10/2019/nl#/Y59.0"

        result = resolvable_label_resolver().load_and_translate_uri(uri)

        assert result == [
            {"term": uri, "term_translation": "Virale vaccins", "lang_code": "nl"}
        ]

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_unknown_code_gives_no_translation(self, mock_get):
        mock_get.return_value = self._response(
            [{"ID": "Y59.1", "label": "Y59.1 Rickettsial vaccines"}]
        )

        assert resolvable_label_resolver().load_and_translate_uri(self.SUBCATEGORY) == []

    @patch("ckanext.fairdatapoint.resolver.requests.get")
    def test_request_failure_gives_no_translation_and_is_not_retried(self, mock_get):
        mock_get.side_effect = Exception("boom")
        resolver = resolvable_label_resolver()

        assert resolver.load_and_translate_uri(self.SUBCATEGORY) == []
        assert resolver.load_and_translate_uri(self.SUBCATEGORY) == []
        assert mock_get.call_count == 1

    @pytest.mark.parametrize(
        "uri",
        [
            "http://icd.who.int/browse10/2019/en",
            "http://example.com/browse10/2019/en#/Y59.0",
            "http://icd.who.int/browse10/2019/en#/not-a-code",
        ],
    )
    def test_other_uris_are_not_routed_to_the_icd_loader(self, uri):
        from ckanext.fairdatapoint.resolver import ICD10_URI_RE

        assert not ICD10_URI_RE.match(uri)


class TestWikidataCanonicalization:
    """Tests for the Wikidata page URI -> entity URI canonicalizer and its wiring
    into `literal_dict_from_graph`."""

    wikidata_data_catalog_path = Path(
        TEST_DATA_DIRECTORY, "wikidata_data_catalog_entry.ttl"
    )

    def test_canonicalize_page_uri(self):
        assert _canonicalize_wikidata_uri(
            "http://www.wikidata.org/wiki/Q327718"
        ) == "http://www.wikidata.org/entity/Q327718"

    def test_canonicalize_https_page_uri(self):
        assert _canonicalize_wikidata_uri(
            "https://www.wikidata.org/wiki/Q327718"
        ) == "http://www.wikidata.org/entity/Q327718"

    def test_canonicalize_property_page_uri(self):
        assert _canonicalize_wikidata_uri(
            "http://www.wikidata.org/wiki/Property:P494"
        ) == "http://www.wikidata.org/entity/P494"

    def test_canonicalize_ignores_entity_uri(self):
        assert _canonicalize_wikidata_uri(
            "http://www.wikidata.org/entity/Q327718"
        ) is None

    def test_canonicalize_ignores_unrelated_host(self):
        assert _canonicalize_wikidata_uri(
            "http://www.example.com/wiki/Q327718"
        ) is None

    def test_canonicalize_ignores_non_entity_pages(self):
        assert _canonicalize_wikidata_uri(
            "https://www.wikidata.org/wiki/Special:EntityData/Q327718"
        ) is None

    def test_canonicalize_host_is_case_insensitive(self):
        assert _canonicalize_wikidata_uri(
            "http://WWW.WIKIDATA.ORG/wiki/Q327718"
        ) == "http://www.wikidata.org/entity/Q327718"

    def test_canonicalize_uri_wrapper_rewrites_page_uri(self):
        assert _canonicalize_uri(
            "http://www.wikidata.org/wiki/Q29937289"
        ) == "http://www.wikidata.org/entity/Q29937289"

    def test_labels_are_found_for_a_page_uri(self):
        """The graph describes the entity URI; looking labels up with the page URI of
        the same item must find them."""
        resolver = resolvable_label_resolver()
        resolver.label_graph = Graph().parse(self.wikidata_data_catalog_path)

        by_page_uri = resolver.literal_dict_from_graph(
            "http://www.wikidata.org/wiki/Q29937289"
        )
        by_entity_uri = resolver.literal_dict_from_graph(
            "http://www.wikidata.org/entity/Q29937289"
        )

        assert by_page_uri
        assert by_page_uri == by_entity_uri
