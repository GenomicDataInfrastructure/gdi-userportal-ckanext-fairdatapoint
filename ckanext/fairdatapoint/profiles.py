# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import datetime, timezone
import re
import json
import logging

from ckanext.dcat.profiles import EuropeanDCATAP2Profile
from ckan.plugins import toolkit
from ckan import model
import dateutil.parser as dateparser
from dateutil.parser import ParserError
from json import JSONDecodeError
from typing import Dict, List
from rdflib import URIRef, Namespace, DCAT, DCTERMS, FOAF

log = logging.getLogger(__name__)

VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")


def _convert_extras_to_declared_schema_fields(dataset_dict: Dict) -> Dict:
    """
    Compares the extras dictionary with the declared schema.
    Updates the declared schema fields with the values that match from the extras.
    Remove the extras that are present on the declared schema.
    :param dataset_dict:
    :return: dataset_dict - Updated dataset_dict
    """
    # Use the correct dataset type, Defaults to 'dataset'
    dataset_type = dataset_dict.get('type', 'dataset')
    # Gets the full Schema definition of the correct dataset type
    context = {'model': model, 'session': model.Session}
    data_dict = {'type': dataset_type}
    full_schema_dict = toolkit.get_action('scheming_dataset_schema_show')(context, data_dict)

    dataset_fields = {x.get('field_name'): x.get('preset') for x in full_schema_dict.get('dataset_fields', [])}

    # Populate the declared schema fields, if they are present in the extras
    for extra_dict in dataset_dict.get('extras', []):
        field_key = extra_dict.get('key')
        field_value = extra_dict.get('value')
        if field_key in dataset_fields:
            preset = dataset_fields[field_key]
            if preset == 'multiple_text' and field_value:
                try:
                    dataset_dict[field_key] = json.loads(field_value)
                except JSONDecodeError:
                    dataset_dict[field_key] = field_value
            elif preset == 'date' and field_value:
                dataset_dict[field_key] = convert_datetime_string(field_value)
            else:
                dataset_dict[field_key] = field_value

    # Remove the extras that have been populated into the declared schema fields
    dataset_dict['extras'] = [d for d in dataset_dict['extras'] if d.get('key') not in dataset_fields]

    return dataset_dict


def validate_tags(values_list: List[Dict]) -> List:
    """
    Validates tags strings to contain allowed characters, replaces others with spaces
    """
    illegal_pattern = re.compile('[^A-Za-z0-9\- _\.]')
    tags = []
    for item in values_list:
        tag_value = item['name']
        if len(tag_value) < 2:
            log.warning(f'Tag {tag_value} is shorter than 2 characters and will be removed')
        elif len(tag_value) > 100:
            log.warning(f'Tag {tag_value} is longer than 100 characters and will be removed')
        else:
            find_illegal = re.search(illegal_pattern, tag_value)
            if find_illegal:
                log.warning(f'Tag {tag_value} contains values other than alphanumeric characters, spaces, hyphens, '
                            f'underscores or dots, they will be replaces with spaces')
                tag = {'name': re.sub(illegal_pattern, ' ', tag_value)}
                tags.append(tag)
            else:
                tags.append(item)
    return tags


def convert_datetime_string(date_value: str) -> datetime:
    """
    Converts datestrings (e.g. '2023-10-06T10:12:55.614000+00:00') to datetime class instance
    """
    try:
        date_value = dateparser.parse(date_value, yearfirst=True)
        if date_value.tzinfo is not None:
            date_value = date_value.astimezone(timezone.utc)
    except ParserError:
        log.error(f'A date field string value {date_value} can not be parsed to a date')
    return date_value


class FAIRDataPointDCATAPProfile(EuropeanDCATAP2Profile):
    """
    An RDF profile for FAIR data points
    """

    def parse_dataset(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        super(FAIRDataPointDCATAPProfile, self).parse_dataset(dataset_dict, dataset_ref)

        dataset_dict = self._parse_creator(dataset_dict, dataset_ref)

        dataset_dict = _convert_extras_to_declared_schema_fields(dataset_dict)

        dataset_dict['tags'] = validate_tags(dataset_dict['tags'])

        return dataset_dict

    def _contact_details(self, subject, predicate):
        """
        Overrides RDFProfile._contact_details so uri is taken from hasUID for VCard
        """
        contact = {}

        for agent in self.g.objects(subject, predicate):
            contact['uri'] = (str(agent) if isinstance(agent, URIRef)
                              else self._get_vcard_property_value(agent, VCARD.hasUID))

            contact['name'] = self._get_vcard_property_value(agent, VCARD.hasFN, VCARD.fn)
            contact['email'] = self._without_mailto(self._get_vcard_property_value(agent, VCARD.hasEmail))
            contact['phone'] = self._get_vcard_property_value(agent, VCARD.hasTelephone)

        return contact

    def _parse_creator(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        graph = self.g
        creators = []
        for creator_ref in graph.objects(dataset_ref, DCTERMS.creator):
            creator = {}
            creator_identifier = graph.value(creator_ref, DCTERMS.identifier)
            creator_name = graph.value(creator_ref, FOAF.name)

            if creator_identifier:
                creator['creator_identifier'] = str(creator_identifier)
            if creator_name:
                creator['creator_name'] = str(creator_name)
            else:
                # If the creator is a URI, use it as the identifier
                if isinstance(creator_ref, URIRef):
                    creator['creator_identifier'] = str(creator_ref)
                    creator['creator_name'] = str(creator_ref)
                else:
                    creator['creator_name'] = str(creator_ref)

            creators.append(creator)

        if len(creators) > 0:
            dataset_dict['creator'] = creators

        return dataset_dict
