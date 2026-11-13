# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import logging
from urllib.parse import urlparse

from ckan.plugins import toolkit
from rdflib import URIRef

from ckanext.fairdatapoint.languages import resolve_languages
from ckanext.fairdatapoint.resolver import resolvable_label_resolver
from ckanext.fairdatapoint.run_scope import forget_finished_runs, run_store

log = logging.getLogger(__name__)

# Registered by ckanext-gdi-userportal; called by name so that this extension needs no import of it.
# It lists the terms of a dataset as the dataset schema marks them (the fields shown as a label), so the labels
# stored at harvest are the ones the catalogue sends out. Without that extension the field lists below are used.
TERMS_ACTION = "gdi_terms_to_translate"

# Dataset fields whose values can be term URIs to resolve. Used when the dataset schema cannot
# say which terms it shows as labels (see TERMS_ACTION).
PACKAGE_REPLACE_FIELDS = [
    "access_rights",
    "applicable_legislation",
    "code_values",
    "coding_system",
    "conforms_to",
    "creator",
    "dataset_status",
    "dcat_type",
    "has_version",
    "health_category",
    "health_theme",
    "frequency",
    "language",
    "legal_basis",
    "personal_data",
    "publisher",
    "publisher_type",
    "purpose",
    "qualified_attribution",
    "qualified_relation",
    "quality_annotation",
    "spatial_coverage",
    "status",
    "theme",
    "type",
    "was_generated_by",
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
    "rights",
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
    "rights",
    "theme",
]

# Languages a source turned out not to have a label in, per term, for the harvest job that is
# running: a term that is missing a language in CKAN is fetched again for every dataset it
# occurs in, so without this a source that has no (say) Dutch label would be asked for it over
# and over. The cache lives for one harvest job only, see `run_scope`.
UNAVAILABLE_LANGUAGES = "unavailable_languages"


def _without_unavailable_languages(
        missing_languages: dict[str, set[str]]
) -> dict[str, set[str]]:
    """Leaves out the languages that this run already found the source does not have"""
    unavailable = run_store(UNAVAILABLE_LANGUAGES, dict)
    if not unavailable:
        return missing_languages

    remaining = {
        term: languages - unavailable.get(term, set())
        for term, languages in missing_languages.items()
    }
    return {term: languages for term, languages in remaining.items() if languages}


def _remember_unavailable_languages(
        missing_languages: dict[str, set[str]], translations: list[dict[str, str]]
) -> None:
    """Remembers, for this run, the missing languages the source did not return"""
    unavailable = run_store(UNAVAILABLE_LANGUAGES, dict)
    if unavailable is None:
        return

    for term, languages in missing_languages.items():
        returned = {t.get("lang_code") for t in translations if t.get("term") == term}
        not_returned = languages - returned
        if not_returned:
            unavailable.setdefault(term, set()).update(not_returned)


NESTED_FIELD_TRANSLATIONS = {
    "qualified_relation": {"role"},
    "qualified_attribution": {"role", "agent"},
    "agent": {"publisher_type", "type", "country"},
    "quality_annotation": {"body"},
    "spatial_coverage": {"uri"},
    "creator": {"publisher_type", "type", "country"},
    "publisher": {"publisher_type", "type", "country"},
    "was_generated_by": {"dct_type"},
}


def resolve_labels(package_dict: dict) -> int:
    """Resolves labels and updates the database

    Parameters
    ----------
    package_dict : dict
        Package dictionary from harvester

    Returns
    -------
    int | None
        Number of translations stored, 0 if none were stored, -1 if no term was
        missing a language. None if CKAN reports an error while storing them.

    """
    translation_list = []

    total_terms = terms_in_package_dict(package_dict)
    forget_finished_runs()
    all_missing_languages = get_missing_languages(total_terms)
    missing_languages = _without_unavailable_languages(all_missing_languages)
    if len(missing_languages) < len(all_missing_languages):
        log.debug(
            "Not asking again for %d term(s) the source has no (more) languages for in this run",
            len(all_missing_languages) - len(missing_languages),
        )

    if missing_languages:
        resolver = resolvable_label_resolver()

        for term in missing_languages:
            extra_translations = resolver.load_and_translate_uri(term)
            translation_list.extend(extra_translations)

        _remember_unavailable_languages(missing_languages, translation_list)

        if translation_list:
            # Only store the languages a term is missing: a translation that is already
            # known (and possibly curated) is left as it is. ignore_auth is set because
            # the harvest runs without a user context.
            filtered_translation_list = [
                t
                for t in translation_list
                if t.get("lang_code") in missing_languages.get(t.get("term"), ())
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
                return len(filtered_translation_list)
        else:
            return 0
    else:
        return -1


def get_missing_languages(
        terms: list[str], languages: list[str] | None = None
) -> dict[str, set[str]]:
    """Gets, per term, the languages CKAN has no translation for yet

    A term that is known in one language but not in another is not resolved: it is
    returned with the languages that are still missing, so those can be added.

    Parameters
    ----------
    terms : list[str]
        List of labels that harvested, that need to be checked if they are resolved
    languages : list[str], optional
        List of language codes that need to be resolved, default is the languages of the catalogue
        (`resolve_languages`: 'en', 'nl' and the form languages of the dataset schema).

    Returns
    -------
    dict[str, set[str]]
        Terms that are missing a translation, with the language codes they are missing.
        Terms that are known in every language are not included.
    """
    languages = list(languages) if languages is not None else list(resolve_languages())
    term_set = set(terms)

    translation_table = toolkit.get_action("term_translation_show")(
        {}, {"terms": term_set, "lang_codes": languages}
    )

    known_languages: dict[str, set[str]] = {}
    for row in translation_table:
        known_languages.setdefault(row["term"], set()).add(row["lang_code"])

    wanted_languages = set(languages)
    return {
        term: wanted_languages - known_languages.get(term, set())
        for term in term_set
        if wanted_languages - known_languages.get(term, set())
    }


def get_list_unresolved_terms(
        terms: list[str], languages: list[str] | None = None
) -> list[str]:
    """This function gets a list of terms not fully known by CKAN, based on an input list

    A term is not fully known if it has no translation in one or more of the languages.

    Parameters
    ----------
    terms : list[str]
        List of labels that harvested, that need to be checked if they are resolved
    languages : list[str], optional
        List of language codes that need to be resolved, default is the languages of the catalogue.

    Returns
    -------
    list[str]
        List containing the labels that are not resolved yet
    """
    return list(get_missing_languages(terms, languages))


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
        True if resolvable URI, False if not
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

def _terms_from_schema(package_dict: dict) -> list[str] | None:
    """The terms the dataset schema says have a label, or None when that cannot be asked.

    None means that the extension that knows the schema is not installed or did not answer; the harvest
    must go on with the field lists of this extension then.
    """
    try:
        action = toolkit.get_action(TERMS_ACTION)
    except Exception:  # not registered (KeyError), or no CKAN app to ask
        return None
    try:
        terms = action({"ignore_auth": True}, {"package": package_dict})["terms"]
    except Exception as error:
        log.warning("Could not ask which terms of the dataset have a label, using the field lists: %s", error)
        return None
    if not isinstance(terms, list):
        return None
    return [term for term in terms if isinstance(term, str)]


def terms_in_package_dict(package_dict: dict) -> list[str]:
    """Extracts list of all terms (including nested) from the dict that could theoretically be resolved as URIs

    The terms are the values of the fields the dataset schema shows as a label (ckanext-gdi-userportal); a
    deployment without it uses the field lists of this module.
    """
    schema_terms = _terms_from_schema(package_dict)
    if schema_terms is not None:
        return [term for term in schema_terms if _is_absolute_uri(term)]

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
