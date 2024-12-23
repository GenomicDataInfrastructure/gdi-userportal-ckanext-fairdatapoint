# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
from typing import Dict, Iterable, Union

import requests
from rdflib import DCAT, DCTERMS, RDF, BNode, Graph, Literal, Namespace, URIRef
from rdflib.term import Node
from requests import HTTPError, JSONDecodeError

from ckanext.fairdatapoint.harvesters.domain.fair_data_point import FairDataPoint
from ckanext.fairdatapoint.harvesters.domain.identifier import Identifier

LDP = Namespace("http://www.w3.org/ns/ldp#")
VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")

log = logging.getLogger(__name__)


class FairDataPointRecordProvider:

    def __init__(self, fdp_end_point: str, harvest_catalogs: bool = False):
        self.fair_data_point = FairDataPoint(fdp_end_point)
        self.harvest_catalogs = harvest_catalogs

    def get_record_ids(self) -> Dict.keys:
        """
        Returns all the FDP records which should end up as packages in CKAN to populate the "guids_in_harvest" list
        https://rdflib.readthedocs.io/en/stable/intro_to_parsing.html
        """
        log.debug(
            "FAIR Data Point get_records from {}".format(
                self.fair_data_point.fdp_end_point
            )
        )

        result = dict()

        fdp_graph = self.fair_data_point.get_graph(self.fair_data_point.fdp_end_point)

        contains_predicate = LDP.contains
        for contains_object in fdp_graph.objects(predicate=contains_predicate):
            result.update(self._process_catalog(str(contains_object)))

        return result.keys()

    def _process_catalog(self, path: Union[str, URIRef]) -> Dict:
        result = dict()

        catalogs_graph = self.fair_data_point.get_graph(path)

        for catalog_subject in catalogs_graph.subjects(RDF.type, DCAT.Catalog):
            identifier = Identifier("")

            identifier.add("catalog", str(catalog_subject))

            if self.harvest_catalogs:
                result[identifier.guid] = catalog_subject

            catalog_graph = self.fair_data_point.get_graph(catalog_subject)

            for dataset_subject in catalog_graph.objects(predicate=DCAT.dataset):
                identifier = Identifier("")

                identifier.add("catalog", str(catalog_subject))

                identifier.add("dataset", str(dataset_subject))

                result[identifier.guid] = dataset_subject

        return result

    def get_record_by_id(self, guid: str) -> str:
        """
        Get additional information for FDP record.
        """
        log.debug(
            "FAIR data point get_record_by_id from {} for {}".format(
                self.fair_data_point.fdp_end_point, guid
            )
        )

        identifier = Identifier(guid)

        subject_url = identifier.get_id_value()

        g = self.fair_data_point.get_graph(subject_url)

        subject_uri = URIRef(subject_url)

        self._remove_fdp_defaults(g, subject_uri)

        # Add information from distribution to graph
        for distribution_uri in g.objects(
            subject=subject_uri, predicate=DCAT.distribution
        ):
            distribution_g = self.fair_data_point.get_graph(distribution_uri)

            self._remove_fdp_defaults(g, distribution_uri)

            for predicate in [
                DCTERMS.description,
                DCTERMS.format,
                DCTERMS.license,
                DCTERMS.title,
                DCAT.accessURL,
            ]:
                for distr_attribute_value in self.get_values(
                    distribution_g, distribution_uri, predicate
                ):
                    g.add((distribution_uri, predicate, distr_attribute_value))

        # Look-up contact information
        for contact_point_uri in self.get_values(g, subject_uri, DCAT.contactPoint):
            if isinstance(contact_point_uri, URIRef):
                self._parse_contact_point(
                    g=g, subject_uri=subject_uri, contact_point_uri=contact_point_uri
                )

        result = g.serialize(format="ttl")

        return result

    @staticmethod
    def _parse_contact_point(g: Graph, subject_uri: URIRef, contact_point_uri: URIRef):
        """
        Replaces contact point URI with a VCard
        """
        g.remove((subject_uri, DCAT.contactPoint, contact_point_uri))
        vcard_node = BNode()
        g.add((subject_uri, DCAT.contactPoint, vcard_node))
        g.add((vcard_node, RDF.type, VCARD.Kind))
        g.add((vcard_node, VCARD.hasUID, contact_point_uri))
        if "orcid" in str(contact_point_uri):
            try:
                orcid_response = requests.get(
                    str(contact_point_uri).rstrip("/") + "/public-record.json"
                )
                json_orcid_response = orcid_response.json()
                name = json_orcid_response["displayName"]
                g.add((vcard_node, VCARD.fn, Literal(name)))
            except (JSONDecodeError, HTTPError) as e:
                log.error(f"Failed to get data from ORCID for {contact_point_uri}: {e}")

    @staticmethod
    def get_values(
        graph: Graph,
        subject: Union[str, URIRef, Node],
        predicate: Union[str, URIRef, Node],
    ) -> Iterable[Node]:
        subject_uri = URIRef(subject)
        predicate_uri = URIRef(predicate)

        for value in graph.objects(subject=subject_uri, predicate=predicate_uri):
            yield value

    @staticmethod
    def _remove_fdp_defaults(g, subject_uri):
        for s, p, o in g.triples((subject_uri, DCTERMS.accessRights, None)):
            access_rights_default = URIRef(f"{subject_uri}#accessRights")
            if o == access_rights_default:
                g.remove((subject_uri, DCTERMS.accessRights, o))
                g.remove((access_rights_default, None, None))
