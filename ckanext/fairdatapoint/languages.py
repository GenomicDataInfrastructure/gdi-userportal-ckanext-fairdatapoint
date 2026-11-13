# SPDX-FileCopyrightText: 2026 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
"""
The languages a harvested label is kept in.

English and Dutch always, plus every language the dataset schema offers in its form
(``form_languages``): the languages the catalogue answers in, so a label the source has in
one of them is stored. It is read from the schema scheming serves, so no setting of this
extension is needed, and a deployment without scheming (or a schema that cannot be read)
keeps English and Dutch.
"""
from __future__ import annotations

import logging

from ckan.plugins import toolkit

log = logging.getLogger(__name__)

DEFAULT_LANGUAGES = ("en", "nl")
DATASET_TYPE = "dataset"


def _code(value) -> str:
    """The primary subtag of a language code, lower case: ``nl_NL`` and ``NL`` give ``nl``."""
    if not isinstance(value, str):
        return ""
    return value.strip().replace("_", "-").split("-", 1)[0].lower()


def resolve_languages() -> tuple[str, ...]:
    """The language codes to resolve labels in: English, Dutch and the form languages of the schema."""
    try:
        schema = toolkit.get_action("scheming_dataset_schema_show")({}, {"type": DATASET_TYPE})
        form_languages = schema.get("form_languages") if isinstance(schema, dict) else None
    except Exception as error:  # no scheming, no such schema: the defaults are right
        log.debug("Could not read the form languages of the dataset schema: %s", error)
        form_languages = None

    extra = [_code(code) for code in form_languages] if isinstance(form_languages, (list, tuple)) else []
    return tuple(dict.fromkeys([*DEFAULT_LANGUAGES, *(code for code in extra if code)]))
