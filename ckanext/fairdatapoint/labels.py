# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import logging
import time
from contextvars import ContextVar
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
# and over. Entries are kept per harvest job and dropped as soon as that job is no longer
# running, so the cache never outlives the harvest of one source.
_unavailable_languages: dict[str, dict[str, set[str]]] = {}
_current_run: ContextVar[str | None] = ContextVar("fairdatapoint_label_run", default=None)
# Seconds between two checks of which harvest jobs are still running
RUN_CHECK_INTERVAL = 30
_last_run_check = 0.0


def start_label_run(run_id: str | None) -> None:
    """Marks the harvest job (run) the labels are resolved for from now on

    Forgets what is cached for runs that have finished in the meantime. Without a run, nothing
    is cached.

    Parameters
    ----------
    run_id : str | None
        Id of the harvest job that is being harvested
    """
    _forget_finished_runs(force=True)
    _current_run.set(run_id)


def _forget_finished_runs(force: bool = False) -> None:
    """Drops the cache of every harvest job that is not running anymore

    A job is marked finished by another process than the one harvesting it, so the database is
    asked rather than relying on a call at the end of the harvest. Unless forced, it is asked
    at most once every `RUN_CHECK_INTERVAL` seconds.
    """
    global _last_run_check

    if not _unavailable_languages:
        return

    now = time.monotonic()
    if not force and now - _last_run_check < RUN_CHECK_INTERVAL:
        return
    _last_run_check = now

    try:
        from ckan import model
        from ckanext.harvest.model import HarvestJob

        running = {
            row[0]
            for row in model.Session.query(HarvestJob.id)
            .filter(HarvestJob.id.in_(list(_unavailable_languages)))
            .filter(HarvestJob.status == "Running")
        }
    except Exception as e:
        log.warning("Could not check which harvest jobs are running: %s", e)
        return

    for run_id in set(_unavailable_languages) - running:
        del _unavailable_languages[run_id]


def _without_unavailable_languages(
        missing_languages: dict[str, set[str]]
) -> dict[str, set[str]]:
    """Leaves out the languages that this run already found the source does not have"""
    unavailable = _unavailable_languages.get(_current_run.get())
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
    run_id = _current_run.get()
    if run_id is None:
        return

    for term, languages in missing_languages.items():
        returned = {t.get("lang_code") for t in translations if t.get("term") == term}
        not_returned = languages - returned
        if not_returned:
            _unavailable_languages.setdefault(run_id, {}).setdefault(term, set()).update(
                not_returned
            )


# Languages to resolve labels in
# TODO language codes should be dynamic
RESOLVE_LANGUAGES = ("en", "nl")

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
    int
        Number of successfully resolved labels, -1 if none needed to be resolved

    """
    translation_list = []

    total_terms = terms_in_package_dict(package_dict)
    _forget_finished_runs()
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

        # Check if there is actually translations in the list
        if translation_list:
            # term_translation_update is a privileged function
            # Thank god CKAN is like Hollywood OS and we can just override
            # Only store the languages a term is missing: a translation that is already
            # known (and possibly curated) is left as it is.
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
                return len(translation_list)
        else:
            return 0
    else:
        return -1


def get_missing_languages(
        terms: list[str], languages: list[str] = RESOLVE_LANGUAGES
) -> dict[str, set[str]]:
    """Gets, per term, the languages CKAN has no translation for yet

    A term that is known in one language but not in another is not resolved: it is
    returned with the languages that are still missing, so those can be added.

    Parameters
    ----------
    terms : list[str]
        List of labels that harvested, that need to be checked if they are resolved
    languages : list[str], optional
        List of language codes that need to be resolved, default is 'en' and 'nl'.

    Returns
    -------
    dict[str, set[str]]
        Terms that are missing a translation, with the language codes they are missing.
        Terms that are known in every language are not included.
    """
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
        terms: list[str], languages: list[str] = RESOLVE_LANGUAGES
) -> list[str]:
    """This function gets a list of terms not fully known by CKAN, based on an input list

    A term is not fully known if it has no translation in one or more of the languages.

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
