# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import logging
from urllib.parse import urlparse

from ckan.plugins import toolkit
from rdflib import URIRef

from ckanext.fairdatapoint.resolver import resolvable_label_resolver

log = logging.getLogger(__name__)

PACKAGE_REPLACE_FIELDS = [
    "access_rights",
    "applicable_legislation", 
    "code_values",
    "coding_system",
    "conforms_to",
    "dcat_type",
    "has_version",
    "health_category",
    "health_theme",
    "frequency",
    "language",
    "legal_basis",
    "personal_data",
    "publisher_type",
    "purpose",
    "qualified_attribution",
    "qualified_relation",
    "quality_annotation",
    "spatial_coverage",
    "status",
    "theme",
    "type",
]
RESOURCE_REPLACE_FIELDS = [
    "access_rights",
    "applicable_legislation", 
    "compress_format",
    "conforms_to",
    "format",
    "hash_algorithm",
    "language",
    "license",
    "mimetype",
    "package_format",
    "status",
]
ACCESS_SERVICES_REPLACE_FIELDS = [
    "access_rights",
    "applicable_legislation", 
    "conforms_to",
    "creator", 
    "format",
    "hvd_category", 
    "language",
    "license", 
    "publisher", 
    "theme", 
]

# Languages to resolve labels in
# TODO language codes should be dynamic
RESOLVE_LANGUAGES = ("en", "nl")

NESTED_FIELD_TRANSLATIONS = {
    "qualified_relation": {"role"},
    "qualified_attribution": {"role"},
    "quality_annotation": {"body"},
    "spatial_coverage": {"uri"},
    "creator": {"publisher_type", "type"},
    "publisher": {"publisher_type", "type"},
}


def resolve_labels(package_dict: dict) -> int:
    """Resolves labels and updates the database

    Parameters
    ----------
    package_dict : dict
        Package dictionary from harvester

    Returns
    -------
    int
        Number of successfully resolved labels, -1 if none needed to be resolved

    """
    translation_list = []

    total_terms = terms_in_package_dict(package_dict)
    unresolved_terms = get_list_unresolved_terms(total_terms)

    if unresolved_terms:
        resolver = resolvable_label_resolver()

        for term in unresolved_terms:
            extra_translations = resolver.load_and_translate_uri(term)
            translation_list.extend(extra_translations)

        # Check if there is actually translations in the list
        if translation_list:
            # term_translation_update is a privileged function
            # Thank god CKAN is like Hollywood OS and we can just override
            # Extra defensive filter: ensure only supported language codes are sent
            filtered_translation_list = [
                t for t in translation_list if t.get("lang_code") in RESOLVE_LANGUAGES
            ]

            if not filtered_translation_list:
                return 0


            updated_labels = toolkit.get_action("term_translation_update_many")(
                {"ignore_auth": True, "defer_commit": True},
                {"data": filtered_translation_list},
            )

            if "success" not in updated_labels:
                log.error("Error updating labels: %s", updated_labels)
            else:
                return len(translation_list)
        else:
            return 0
    else:
        return -1


def get_list_unresolved_terms(
        terms: list[str], languages: list[str] = RESOLVE_LANGUAGES
) -> list[str]:
    """This function gets a list of terms not fully known by CKAN, based on an input list

    If a label is present in one language but missing in another, it is considered resolved:
    reason being that the language most likely does not exist for a given label, if one was
    resolved successfully before.

    Parameters
    ----------
    terms : list[str]
        List of labels that harvested, that need to be checked if they are resolved
    languages : list[str], optional
        List of language codes that need to be resolved, default is 'en' and 'nl'.

    Returns
    -------
    list[str]
        List containing the labels that are not resolved yet
    """
    term_set = set(terms)

    translation_table = toolkit.get_action("term_translation_show")(
        {}, {"terms": term_set, "lang_codes": languages}
    )

    known_terms = set(x["term"] for x in translation_table)
    unknown_terms = term_set - known_terms

    return list(unknown_terms)


def _is_absolute_uri(uri: str) -> bool:
    """Checks if a given URI is an absolute http or https URI.

    Checks for three things:
    1. Scheme is either `http` or `https`
    2. A netloc is defined (domain name)
    3. A path is defined

    Parameters
    ----------
    uri : str
        URI that needs to be checked

    Returns
    -------
    bool
        True if resolvale URI, False if not
    """
    try:
        # If URI cannot be parsed we can safely assume it's invalid
        parsed_uri = urlparse(uri)
    except (ValueError, AttributeError):
        return False

    parsable = bool(
        parsed_uri.scheme in ["http", "https"] and parsed_uri.netloc and parsed_uri.path
    )
    return parsable


def _append_value(term_list, val):
    # helper to append single or list values
    if isinstance(val, list):
        for v in val:
            if isinstance(v, URIRef):
                term_list.append(str(v))
            elif isinstance(v, str):
                term_list.append(v)
    elif isinstance(val, URIRef):
        term_list.append(str(val))
    elif isinstance(val, str):
        term_list.append(val)
    return term_list


def _collect_values_for_field(field: str, value, term_list: list) -> list:
    if value is None:
        return term_list
    nested_fields = NESTED_FIELD_TRANSLATIONS.get(field)
    if isinstance(value, list):
        for item in value:
            if nested_fields and isinstance(item, dict):
                for nested_field in nested_fields:
                    if nested_field in item:
                        term_list = _collect_values_for_field(
                            nested_field, item[nested_field], term_list
                        )
            else:
                term_list = _append_value(term_list, item)
        return term_list
    if isinstance(value, dict):
        if nested_fields:
            for nested_field in nested_fields:
                if nested_field in value:
                    term_list = _collect_values_for_field(
                        nested_field, value[nested_field], term_list
                    )
        return term_list
    return _append_value(term_list, value)

def _select_and_append_values(data_item: dict, fields_list: list, term_list: list) -> list:
    for key, value in data_item.items():
        if key in fields_list:
            term_list = _collect_values_for_field(key, value, term_list)
    return term_list

def terms_in_package_dict(package_dict: dict) -> list[str]:
    """Extracts list of all terms (including nested) from the dict that could theoretically be resolved as URIs"""
    term_list = []
    term_list = _select_and_append_values(package_dict, PACKAGE_REPLACE_FIELDS, term_list)
    resources = package_dict.get("resources")
    if resources and isinstance(resources, list):
        for res in resources:
            if not isinstance(res, dict):
                continue
            term_list = _select_and_append_values(res, RESOURCE_REPLACE_FIELDS, term_list)
            access_services = res.get("access_services")
            if access_services and isinstance(access_services, list):
                for svc in access_services:
                    if not isinstance(svc, dict):
                        continue
                    term_list = _select_and_append_values(svc, ACCESS_SERVICES_REPLACE_FIELDS, term_list)
    valid_term_list = [term for term in term_list if _is_absolute_uri(term)]
    return valid_term_list
