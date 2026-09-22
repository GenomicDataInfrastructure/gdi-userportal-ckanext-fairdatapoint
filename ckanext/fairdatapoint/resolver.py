# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import logging
import re
from typing import Callable

import requests
from rdflib import RDFS, SDO, SKOS, Graph, URIRef
from urllib.parse import urlparse
from ckanext.fairdatapoint.harvesters.config import get_bioportal_api_key

log = logging.getLogger(__name__)


# Default language for a label if it is not defined (Literal without language tag)
DEFAULT_LABEL_LANG = "en"
LANG_LIST = ["en", "nl"]
SKIP_URIS: set[str] = set()
REQUEST_TIMEOUT = 100  # seconds

# DPV is published as versioned, non-content-negotiable GitHub Pages docs (the org
# also moved from w3c.github.io to w3c-cg.github.io), but every term also has a
# canonical https://w3id.org/dpv... identifier that *does* content-negotiate and
# always resolves to the current DPV release. Doc-page URIs are rewritten to their
# w3id.org equivalent so DPV terms resolve regardless of which GitHub Pages mirror
# or version a harvested source happened to reference.
DPV_DOC_HOSTS = {"w3c.github.io", "w3c-cg.github.io"}
DPV_DOC_PATH_RE = re.compile(r"^/dpv/(?P<version>[^/]+)/(?P<module>[^/]+)/?$")


def _canonicalize_dpv_uri(uri_str: str) -> str | None:
    """Rewrites a DPV GitHub Pages doc-page URI to its resolvable w3id.org URI.

    Parameters
    ----------
    uri_str : str
        URI to check and possibly rewrite

    Returns
    -------
    str | None
        The canonical https://w3id.org/dpv... URI if `uri_str` looks like a DPV
        doc-page URI (e.g. https://w3c-cg.github.io/dpv/2.1/dpv/#Term), otherwise
        None.
    """
    parsed_uri = urlparse(uri_str)
    if parsed_uri.netloc not in DPV_DOC_HOSTS:
        return None

    match = DPV_DOC_PATH_RE.match(parsed_uri.path)
    if not match:
        return None

    module = match.group("module")
    canonical = "https://w3id.org/dpv" if module == "dpv" else f"https://w3id.org/dpv/{module}"
    if parsed_uri.fragment:
        canonical += f"#{parsed_uri.fragment}"
    return canonical


# Ordered list of URI canonicalizers: pure rewrites applied, in order, before a URI
# is fetched or matched against a graph. Add an entry here when a host publishes doc
# pages that don't content-negotiate but does have a resolvable canonical URI
# elsewhere -- see `_canonicalize_dpv_uri` for the pattern to follow. The first
# canonicalizer to return a non-None result wins.
URI_CANONICALIZERS: list[Callable[[str], str | None]] = [
    _canonicalize_dpv_uri,
]


def _canonicalize_uri(uri_str: str) -> str:
    """Rewrites `uri_str` via the first matching entry in `URI_CANONICALIZERS`.

    Returns `uri_str` unchanged if no canonicalizer matches.
    """
    for canonicalize in URI_CANONICALIZERS:
        canonical = canonicalize(uri_str)
        if canonical:
            return canonical
    return uri_str


class resolvable_label_resolver:
    """Generic label resolver class

    This class implements a generic label resolver. It consists of three functions:
    1. load_graph
    2. literal_dict_from_graph
    3. load_and_translate_uri

    The functions are made for the generic case: assuming the subject URI is resolvable and will
    return an RDF document when accessed using content negotiation. This can work for some of the
    European labels (HVD themes for example) and also for Wikidata.

    Two extension points cover cases the generic loader can't handle on its own:

    - A host publishes doc pages that don't content-negotiate, but does have a resolvable
      canonical URI elsewhere (e.g. DPV's GitHub Pages docs vs. its w3id.org PURLs): add a
      rewrite function to the module-level `URI_CANONICALIZERS` list (see `_canonicalize_dpv_uri`
      for the pattern). It runs before every fetch and every graph lookup, so it only needs to be
      registered once.
    - A host needs bespoke fetching -- custom headers, authentication, a non-standard endpoint --
      rather than a simple URI rewrite (e.g. Wikidata, BioOntology): add a `_load_*_graph` method
      following the existing `_load_wikidata_graph`/`_load_bioontology_graph` pattern and register
      it in the module-level `CUSTOM_LOADERS` list.
    """

    def __init__(self) -> None:
        self.label_graph = Graph()

    def literal_dict_from_graph(self, subject: str | URIRef) -> dict:
        """Turns a Graph into a dictionary with key: language, value: label

        This function traverses Graph g to find the labels for a given subject.
        It looks at the following namespaces in order:
            1. Schema.org name
            2. RDF-scheme label
            3. SKOS prefLabel

        All found labels and languages are stored in a dictionary. See this example for the format:
        ```
        {
          "nl": "Albus Perkamentus",
          "en": "Albus Dumbledore"
        }
        ```

        Literals without a language tag are normalized to `DEFAULT_LABEL_LANG`. Only languages
        present in `LANG_LIST` will be included; others are skipped. If there are multiple
        labels for the same language the last one seen will overwrite the previous.

        Parameters
        ----------
        subject : str | URIRef
            subject for which the label is to be extracted

        Returns
        -------
        dict
            Dictionary containing labels with language as key, localized label as value
        """
        lang_dict = dict()
        subject = URIRef(_canonicalize_uri(str(subject)))

        # I am aware the dictionary gets overwritten. I am assuming SKOS.prefLabel is the most
        # "authortive" one and therefore it will overwrite the preceding labels.
        for label_predicate in [SDO.name, RDFS.label, SKOS.prefLabel]:
            if (subject, label_predicate, None) in self.label_graph:
                # Check if it contains label_predicate for the subject
                for x in self.label_graph.objects(
                    subject=subject,
                    predicate=label_predicate,
                ):
                    # Normalize missing language to DEFAULT_LABEL_LANG
                    lang = x.language or DEFAULT_LABEL_LANG
                    # Only keep languages we explicitly support
                    if lang in LANG_LIST:
                        lang_dict[lang] = x.value

        return lang_dict

    def _load_wikidata_graph(self, uri: str) -> bool:
        """Load RDF from Wikidata using Special:EntityData endpoint.

        Parameters
        ----------
        uri : str
            Wikidata URI (either /entity/ or /wiki/ format)

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        parsed_uri = urlparse(uri)
        entity_id = None

        if parsed_uri.path.startswith("/entity/"):
            entity_id = parsed_uri.path.split("/entity/")[-1]
        elif parsed_uri.path.startswith("/wiki/"):
            entity_id = parsed_uri.path.split("/wiki/")[-1]

        if not entity_id:
            return False

        try:
            wikidata_url = (
                f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}"
            )
            headers = {
                "Accept": "text/turtle",
                "User-Agent": "ckanext-fairdatapoint/harvester",
            }
            response = requests.get(
                wikidata_url, headers=headers, timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            self.label_graph.parse(data=response.text, format="turtle")
            return True
        except Exception as e:
            log.warning("Error loading Wikidata URI %s: %s", uri, str(e))
            return False

    def _load_bioontology_graph(self, uri: str) -> bool:
        """Load RDF from BioOntology API using JSON-LD format.

        Parameters
        ----------
        uri : str
            BioOntology concept URI

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        if "/ontology/" not in uri:
            log.warning("BioOntology URI does not contain '/ontology/': %s", uri)
            return False
        
        try:
            ontology = uri.split("/ontology/")[1].split("/")[0]
            encoded_concept = requests.utils.quote(uri, safe='')
            url = f"https://data.bioontology.org/ontologies/{ontology}/classes/{encoded_concept}"
            api_key = get_bioportal_api_key()

            if not api_key:
                log.error("BioPortal API key is not configured. Cannot fetch data from BioOntology.")
                return False

            headers = {
                "Accept": "application/json",
                "Authorization": f"apikey token={api_key}"
            }
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

            if response.status_code == 200:
                self.label_graph.parse(data=response.text, format="json-ld")
                return True
            else:
                log.error("Failed to fetch BioOntology data: %s", response.status_code)
                return False
        except Exception as e:
            log.warning("Error loading BioOntology URI %s: %s", uri, str(e))
            return False

    def _load_generic_graph(self, uri: str) -> bool:
        """Load RDF from a generic HTTP URI with format negotiation.

        Attempts parsing with multiple formats: default (auto-detect),
        XML, and Turtle.

        Parameters
        ----------
        uri : str
            HTTP URI to load

        Returns
        -------
        bool
            True if successful, False otherwise
        """
        try:
            headers = {
                "Accept": (
                    "text/turtle, "
                    "application/ld+json, "
                    "application/rdf+xml;q=0.9, "
                    "application/n-triples;q=0.8, "
                    "*/*;q=0.1"
                )
            }
            response = requests.get(uri, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()

            # Try parsing with multiple formats
            for fmt in [None, "xml", "turtle", "json-ld"]:
                try:
                    if fmt:
                        self.label_graph.parse(data=response.text, format=fmt)
                    else:
                        self.label_graph.parse(data=response.text)
                    return True
                except Exception:
                    continue

            log.warning("Failed to parse URI %s with any format", uri)
            return False
        except Exception as e:
            log.warning("Error fetching URI %s: %s", uri, str(e))
            return False

    def load_graph(self, uri: str | URIRef, empty_graph: bool = False) -> Graph:
        """Load RDF graph from a URI using appropriate method based on domain.

        Parameters
        ----------
        uri : str | URIRef
            URI of graph to load
        empty_graph : bool, optional
            Empty current graph when loading, by default False

        Returns
        -------
        Graph
            Loaded Graph
        """
        uri_str = _canonicalize_uri(str(uri))

        if uri_str in SKIP_URIS:
            return self.label_graph

        if empty_graph:
            del self.label_graph
            self.label_graph = Graph()

        try:
            for matches, loader_name in CUSTOM_LOADERS:
                if matches(uri_str):
                    loader = getattr(self, loader_name)
                    if loader(uri_str):
                        return self.label_graph
                    SKIP_URIS.add(uri_str)
                    return self.label_graph

            # No custom loader matched, fall back to generic HTTP loading
            if self._load_generic_graph(uri_str):
                return self.label_graph
            else:
                SKIP_URIS.add(uri_str)
                return self.label_graph

        except Exception as e:
            log.warning("Error loading graph from %s: %s", uri_str, str(e))
            SKIP_URIS.add(uri_str)
        return self.label_graph

    def load_and_translate_uri(self, subject_uri: str | URIRef) -> list[dict[str, str]]:
        """Loads the RDF graph for a given subject, extracts labels

        Parameters
        ----------
        subject_uri : str | URIRef
            Subject URI that the labels need to be extracted for

        Returns
        -------
        list[dict[str, str]]
            List of dictionaries in the format of CKAN function `term_translation_update_many`
        """
        # `load_graph` and `literal_dict_from_graph` each canonicalize `subject_uri`
        # internally (see `_canonicalize_uri`), so translations still get stored
        # against the original, un-rewritten `subject_uri` below -- matching
        # whatever URI the harvested data actually references.
        self.load_graph(subject_uri)
        translation_dict = self.literal_dict_from_graph(subject_uri)
        ckan_translation_list = []

        """
        Now turn the dictionary into CKAN format
        It should be as follows:

        Parameters:
        term (string) - the term to be translated, in the original language, e.g. 'romantic novel'
        term_translation (string) - the translation of the term, e.g. 'Liebesroman'
        lang_code (string) - the language code of the translation, e.g. 'de'
        """
        for language, label in translation_dict.items():
            # only append allowed languages
            if language and language in LANG_LIST:
                ckan_translation_list.append(
                    {
                        "term": str(subject_uri),
                        "term_translation": label,
                        "lang_code": language,
                    }
                )

        return ckan_translation_list


# Ordered list of custom loaders: (matcher, loader method name) pairs for hosts that
# need bespoke fetching (custom headers, auth, a non-standard endpoint) rather than a
# simple URI rewrite. `load_graph` calls the loader method of the first matching
# entry instead of falling back to `_load_generic_graph`. Method names are looked up
# via `getattr` at call time so this can be declared right after the class body.
CUSTOM_LOADERS: list[tuple[Callable[[str], bool], str]] = [
    (
        lambda uri: urlparse(uri).netloc in {"wikidata.org", "www.wikidata.org"},
        "_load_wikidata_graph",
    ),
    (
        lambda uri: bool(re.search(r"bioontology\.org", uri, re.IGNORECASE)),
        "_load_bioontology_graph",
    ),
]
