# SPDX-FileCopyrightText: 2026 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from unittest.mock import patch

import pytest

from ckanext.fairdatapoint.languages import resolve_languages


def _schema(schema):
    return patch("ckanext.fairdatapoint.languages.toolkit.get_action", return_value=lambda context, data: schema)


@pytest.mark.parametrize(
    ["schema", "expected"],
    [
        ({"form_languages": ["en"]}, ("en", "nl")),
        ({"form_languages": ["en", "nl"]}, ("en", "nl")),
        ({"form_languages": ["en", "de"]}, ("en", "nl", "de")),
        ({"form_languages": ["nl_NL", "FR", " de-AT "]}, ("en", "nl", "fr", "de")),
        ({"form_languages": ["", None, 5]}, ("en", "nl")),
        ({}, ("en", "nl")),
        ({"form_languages": "de"}, ("en", "nl")),
        (None, ("en", "nl")),
    ],
)
def test_the_languages_are_english_dutch_and_the_form_languages_of_the_schema(schema, expected):
    with _schema(schema):
        assert resolve_languages() == expected


@pytest.mark.parametrize("error", [KeyError("no such action"), RuntimeError("no app"), Exception("anything")])
def test_a_schema_that_cannot_be_read_keeps_english_and_dutch(error):
    with patch("ckanext.fairdatapoint.languages.toolkit.get_action", side_effect=error):
        assert resolve_languages() == ("en", "nl")


def test_the_dataset_schema_is_asked_for():
    asked = []

    def action(context, data):
        asked.append(data)
        return {"form_languages": ["en"]}

    with patch("ckanext.fairdatapoint.languages.toolkit.get_action", return_value=action) as get_action:
        resolve_languages()

    get_action.assert_called_once_with("scheming_dataset_schema_show")
    assert asked == [{"type": "dataset"}]
