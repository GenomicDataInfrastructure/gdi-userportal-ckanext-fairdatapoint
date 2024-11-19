# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

from datetime import datetime, timezone
import re
import json
import logging

from ckanext.dcat.profiles import EuropeanDCATAP3Profile
from ckan.plugins import toolkit
from ckan import model
import dateutil.parser as dateparser
from dateutil.parser import ParserError
from json import JSONDecodeError
from typing import Dict, List
from rdflib import URIRef, Namespace, DCAT, DCTERMS, FOAF

log = logging.getLogger(__name__)

VCARD = Namespace("http://www.w3.org/2006/vcard/ns#")

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


class FAIRDataPointDCATAPProfile(EuropeanDCATAP3Profile):
    """
    An RDF profile for FAIR data points
    """

    def parse_dataset(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        super(FAIRDataPointDCATAPProfile, self).parse_dataset(dataset_dict, dataset_ref)

        dataset_dict['tags'] = validate_tags(dataset_dict['tags'])

        return dataset_dict
