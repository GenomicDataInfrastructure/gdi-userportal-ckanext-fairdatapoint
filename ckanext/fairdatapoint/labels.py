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
    "conforms_to",
    "has_version",
    "language",
    "spatial_uri",
    "theme",
]

# Languages to resolve labels in
# TODO language codes should be dynamic
RESOLVE_LANGUAGES = ("en", "nl")


def get_list_unresolved_terms(
    terms: list[str], languages=RESOLVE_LANGUAGES
) -> list[str]:
    """This function gets a list of terms not known by CKAN, based on an input list

    Parameters
    ----------
    terms : list[str]
        List of labels that harvested, that need to be checked if they are resolved

    Returns
    -------
    list[str]
        List containing the labels that are resolved
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


def terms_in_package_dict(package_dict: dict) -> list[str]:
    """Extracts list of all terms from a dictionary that could theoretically be resolved

    Parameters
    ----------
    package_dict : dict
        Package dictionary that is harvested and parsed by a profile

    Returns
    -------
    list[str]
        List of URIs that could theoretically be resolved
    """
    term_list = []

    for key in PACKAGE_REPLACE_FIELDS:
        if values := package_dict.get(key):
            if isinstance(values, list):
                term_list.extend(values)
            elif isinstance(values, str) or isinstance(values, URIRef):
                term_list.append(values)

    # Now filter if URI and only return URIs
    valid_term_list = [term for term in term_list if _is_absolute_uri(term)]
    return valid_term_list


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
    log.debug("Label resolving is requested")
    translation_list = []

    total_terms = terms_in_package_dict(package_dict)
    unresolved_terms = get_list_unresolved_terms(total_terms)

    if unresolved_terms:
        log.debug("There are %d unresolved terms", len(unresolved_terms))

        resolver = resolvable_label_resolver()

        for term in unresolved_terms:
            extra_translations = resolver.load_and_translate_uri(term)
            translation_list.extend(extra_translations)

        # Check if there is actually translations in the list
        if translation_list:
            log.debug("Resolved %d labels", len(translation_list))

            # term_translation_update is a privileged function
            # Thank god CKAN is like Hollywood OS and we can just override
            updated_labels = toolkit.get_action("term_translation_update_many")(
                {"ignore_auth": True, "defer_commit": True},
                {"data": translation_list},
            )

            if "success" not in updated_labels:
                log.warning("Error updating labels: %s", updated_labels)

            elif not (len(translation_list) == int(updated_labels["success"])):
                log.warning(
                    "Of %d labels, only %d updated successfully",
                    len(translation_list),
                    updated_labels["success"],
                )
            else:
                log.debug("Updated %s labels in database", updated_labels["success"])
                return len(translation_list)
        else:
            log.debug("No labels succesfully resolved")
            return 0
    else:
        log.debug("There are no unresolved terms!")
        return -1


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
