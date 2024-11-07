# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
import json
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Dict, List

import dateutil.parser as dateparser
from ckan import model
from ckan.plugins import toolkit
from dateutil.parser import ParserError
from rdflib import DCAT, DCTERMS, FOAF, Namespace, URIRef

from ckanext.dcat.profiles import EuropeanDCATAP3Profile
from ckanext.fairdatapoint.resolver import PACKAGE_REPLACE_FIELDS

log = logging.getLogger(__name__)

VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")

WIKIDATA_DOMAINS = ["wikidata.org", "www.wikidata.org"]


def validate_tags(values_list: List[Dict]) -> List:
    """
    Validates tags strings to contain allowed characters, replaces others with spaces
    """
    illegal_pattern = re.compile("[^A-Za-z0-9\- _\.]")
    tags = []
    for item in values_list:
        tag_value = item["name"]
        if len(tag_value) < 2:
            log.warning(
                f"Tag {tag_value} is shorter than 2 characters and will be removed"
            )
        elif len(tag_value) > 100:
            log.warning(
                f"Tag {tag_value} is longer than 100 characters and will be removed"
            )
        else:
            find_illegal = re.search(illegal_pattern, tag_value)
            if find_illegal:
                log.warning(
                    f"Tag {tag_value} contains values other than alphanumeric characters, spaces, hyphens, "
                    f"underscores or dots, they will be replaces with spaces"
                )
                tag = {"name": re.sub(illegal_pattern, " ", tag_value)}
                tags.append(tag)
            else:
                tags.append(item)
    return tags


class FAIRDataPointDCATAPProfile(EuropeanDCATAP3Profile):
    """
    An RDF profile for FAIR data points
    """

    def parse_dataset(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        super(FAIRDataPointDCATAPProfile, self).parse_dataset(dataset_dict, dataset_ref)

        # dataset_dict = self._parse_contact_point(dataset_dict, dataset_ref)
        dataset_dict = self._parse_creator(dataset_dict, dataset_ref)

        ## dataset_dict = _convert_extras_to_declared_schema_fields(dataset_dict)

        dataset_dict["tags"] = validate_tags(dataset_dict["tags"])

        return dataset_dict

    def _contact_point_details(self, subject, predicate) -> List:
        """
        Overrides RDFProfile._contact_details so uri is taken from hasUID for VCard
        """
        contact_list = []

        for agent in self.g.objects(subject, predicate):
            contact = {
                "uri": (
                    str(agent)
                    if isinstance(agent, URIRef)
                    else self._get_vcard_property_value(agent, VCARD.hasUID)
                ),
                "name": self._get_vcard_property_value(agent, VCARD.hasFN, VCARD.fn),
                "email": self._without_mailto(
                    self._get_vcard_property_value(agent, VCARD.hasEmail)
                ),
            }

            contact_list.append(contact)

        return contact_list

    def _parse_contact_point(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        """
        ckan-dcat extension implies there can be just one contact point and in case a list is provided by source only
        last value is taken. Besides it never solves uri from a VCard object. This function parses DCAT.contactPoint
        information to a list of `pontact_point` dictionaries and replaces ckan-dcat values
        """
        contact_point = self._contact_point_details(
            subject=dataset_ref, predicate=DCAT.contactPoint
        )
        dcat_profile_contact_fields = ["contact_name", "contact_email", "contact_uri"]
        if contact_point:
            dataset_dict["extras"].append(
                {"key": "contact_point", "value": contact_point}
            )
            # Remove the extras contact_ fields if they were parsed by dcat extension
            dataset_dict["extras"] = [
                item
                for item in dataset_dict["extras"]
                if item.get("key") not in dcat_profile_contact_fields
            ]
        return dataset_dict

    def _parse_creator(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        graph = self.g
        creators = []
        for creator_ref in graph.objects(dataset_ref, DCTERMS.creator):
            creator = {}
            creator_identifier = graph.value(creator_ref, DCTERMS.identifier)
            creator_name = graph.value(creator_ref, FOAF.name)

            if creator_identifier:
                creator["identifier"] = str(creator_identifier)
            if creator_name:
                creator["name"] = str(creator_name)
            else:
                # If the creator is a URI, use it as the identifier
                if isinstance(creator_ref, URIRef):
                    creator["identifier"] = str(creator_ref)
                    creator["name"] = str(creator_ref)
                else:
                    creator["name"] = str(creator_ref)

            creators.append(creator)

        if len(creators) > 0:
            dataset_dict["creator"] = creators

        return dataset_dict

    @staticmethod
    def _rewrite_wikidata_url(uri: str) -> str:
        """This function fixes Wikidata URIs to use references instead of web URI

        It is necessary to fix this for label resolving, as subject in the graph won't match
        """
        # URL
        try:
            parsed_url = urllib.parse.urlparse(uri)

            if (
                parsed_url.scheme.startswith("http")
                and parsed_url.netloc in WIKIDATA_DOMAINS
                and parsed_url.path.startswith("/wiki/")
            ):
                # Find the entity ID; which comes after the /wiki/ part of the URI
                entity_id = parsed_url.path[len("/wiki/") :]
                # Make sure it is an actualy valid entity ID, they always start with a letter,
                # followed by numbers. See https://www.wikidata.org/wiki/Wikidata:Identifiers
                # Items typically start with a Q, but let's stay flexible.
                if re.fullmatch("[a-zA-Z]\d+", entity_id):
                    # All conditions are met. We can rewrite the Wikidata url.
                    new_url = f"http://www.wikidata.org/entity/{entity_id}"

                    return new_url
        except ValueError:
            pass

        return uri

    def _fix_wikidata_uris(self, dataset_dict: dict, fields_list: list[str]):
        for field in fields_list:
            value = dataset_dict.get(field)
            new_value = None
            if value:
                if isinstance(value, List):
                    new_value = [self._rewrite_wikidata_url(uri) for uri in value]
                else:
                    new_value = self._rewrite_wikidata_url(value)
            dataset_dict[field] = new_value
        return dataset_dict
