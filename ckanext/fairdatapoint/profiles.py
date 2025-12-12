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

        dataset_dict = self._fix_wikidata_uris(dataset_dict, PACKAGE_REPLACE_FIELDS)

        dataset_dict = self._filter_conforms_to(dataset_dict)

        resolve_labels(dataset_dict)

        return dataset_dict

    def _sanitize_tags_translated(tags_translated: Dict[str, List[str]]) -> Dict[str, List[str]]:
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
                    rewritten = []
                    for uri in value:
                        if isinstance(uri, str):
                            rewritten.append(self._rewrite_wikidata_url(uri))
                        else:
                            rewritten.append(uri)
                    new_value = rewritten
                elif isinstance(value, str):
                    new_value = self._rewrite_wikidata_url(value)
                else:
                    new_value = value
                dataset_dict[field] = new_value
        return dataset_dict

    def _filter_conforms_to(self, dataset_dict: Dict) -> Dict:
        """
        Filter conforms_to field by removing values that match the profile URI pattern.
        """
        conforms_to = dataset_dict.get("conforms_to")
        if conforms_to:
            filtered_values = []

            # Handle both single string and list of strings
            values_to_filter = (
                conforms_to if isinstance(conforms_to, list) else [conforms_to]
            )

            for value in values_to_filter:
                if isinstance(value, str):
                    # Check if the value matches the pattern: http(s), optional fdp, and profile
                    if not self._should_remove_conforms_to_value(value):
                        filtered_values.append(value)
                else:
                    filtered_values.append(value)

            # Update the dataset_dict with the filtered values
            if filtered_values:
                dataset_dict["conforms_to"] = (
                    filtered_values
                    if isinstance(conforms_to, list)
                    else (filtered_values[0] if filtered_values else None)
                )
            else:
                dataset_dict.pop("conforms_to", None)

        return dataset_dict

    def _should_remove_conforms_to_value(value: str) -> bool:
        """
        Check if a conforms_to value should be removed using regex pattern matching.

        Removes values that match the pattern:
        - Start with http:// or https://
        - Contain the word "profile"
        """
        # Pattern explanation:
        # ^https?:\/\/ - starts with 'http://' or 'https://'
        # .* - any characters in between
        # \/profile\/ - '/profile/' somewhere in the URL
        pattern = r"^https?:\/\/.*\/profile\/"
        return bool(re.match(pattern, value, re.IGNORECASE))
