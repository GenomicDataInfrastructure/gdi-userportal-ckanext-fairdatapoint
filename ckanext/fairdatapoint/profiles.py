# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
import logging
import re
import urllib.parse
from typing import Dict, List

from rdflib import Namespace, URIRef

from ckanext.dcat.profiles import EuropeanHealthDCATAPProfile
from ckanext.fairdatapoint.labels import PACKAGE_REPLACE_FIELDS, resolve_labels

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


class FAIRDataPointDCATAPProfile(EuropeanHealthDCATAPProfile):
    """
    An RDF profile for FAIR data points
    """

    def parse_dataset(self, dataset_dict: Dict, dataset_ref: URIRef) -> Dict:
        super(FAIRDataPointDCATAPProfile, self).parse_dataset(dataset_dict, dataset_ref)

        tags_translated = dataset_dict.get("tags_translated")
        if isinstance(tags_translated, dict):
            dataset_dict["tags_translated"] = self._sanitize_tags_translated(
                tags_translated
            )

            default_lang_tags = dataset_dict["tags_translated"].get(
                self._default_lang
            ) or next(
                (
                    values
                    for values in dataset_dict["tags_translated"].values()
                    if values
                ),
                [],
            )
            dataset_dict["tags"] = [{"name": tag} for tag in default_lang_tags]

        dataset_dict["tags"] = validate_tags(dataset_dict.get("tags", []))

        resolve_labels(dataset_dict)

        return dataset_dict

    def _sanitize_tags_translated(
        self, tags_translated: Dict[str, List[str]]
    ) -> Dict[str, List[str]]:
        """Remove invalid multilingual tags to satisfy CKAN length rules."""

        sanitized: Dict[str, List[str]] = {}

        for lang, values in tags_translated.items():
            tag_dicts = [{"name": value} for value in values if value]
            cleaned = validate_tags(tag_dicts)
            sanitized[lang] = [tag["name"] for tag in cleaned]

            if len(values) != len(sanitized[lang]):
                removed_tags = [v for v in values if v not in sanitized[lang]]
                log.warning(
                    "Removed invalid tags for language %s during multilingual sanitation. Original: %r, Removed: %r",
                    lang,
                    values,
                    removed_tags,
                )

        return sanitized
