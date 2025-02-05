# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from datetime import datetime
from dateutil.tz import tzutc
from pathlib import Path
from unittest.mock import patch

from docopt import extras
from rdflib import Graph
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
class TestProcessors:
    @patch("ckanext.fairdatapoint.processors.FairDataPointRDFParser.datasets")
    def test_fdp_record_converter_dataset(self, parser_datasets):
        fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
        data = Graph().parse(Path(TEST_DATA_DIRECTORY, "Project_27866022694497978_out.ttl")).serialize()
        fdp_record_to_package.record_to_package(guid="catalog=https://covid19initiatives.health-ri.nl/p/"
                                                     "ProjectOverview?focusarea=http://purl.org/zonmw/generic/10006;"
                                                     "dataset=https://covid19initiatives.health-ri.nl/p/Project/"
                                                     "27866022694497978",
                                                record=data)
        assert parser_datasets.called

    @patch("ckanext.fairdatapoint.processors.FairDataPointRDFParser.catalogs")
    def test_fdp_record_converter_catalog(self, parser_catalogs):
        fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
        data = Graph().parse(Path(TEST_DATA_DIRECTORY, "fdp_catalog.ttl")).serialize()
        fdp_record_to_package.record_to_package(
            guid="catalog=https://fair.healthinformationportal.eu/catalog/1c75c2c9-d2cc-44cb-aaa8-cf8c11515c8d",
            record=data)
        assert parser_catalogs.called

    def test_fdp_record_converter_dataset_dict(self):
        fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
        data = Graph().parse(Path(TEST_DATA_DIRECTORY, "Project_27866022694497978_out.ttl")).serialize()
        actual_dataset = fdp_record_to_package.record_to_package(
            guid="catalog=https://covid19initiatives.health-ri.nl/p/ProjectOverview?focusarea="
                 "http://purl.org/zonmw/generic/10006;"
                 "dataset=https://covid19initiatives.health-ri.nl/p/Project/27866022694497978",
            record=data)
        expected_dataset = dict(extras=[], uri="https://covid19initiatives.health-ri.nl/p/Project/27866022694497978",
                                resources=[], title="COVID-NL cohort MUMC+",
                                notes="Clinical data of MUMC COVID-NL cohort", tags=[],
                                license_id="", identifier="27866022694497978",
                                has_version=[
                                    "https://repo.metadatacenter.org/template-instances/2836bf1c-76e9-44e7-a65e-80e9ca63025a"],
                                contact=[{'email': '', 'identifier': 'https://orcid.org/0000-0002-4348-707X', 'name': 'N.K. De Vries','uri': '', 'url': ''}
                                ], creator=[{'email': '', 'identifier': '', 'name': '', 'type': '', 'uri': 'https://orcid.org/0000-0002-0180-3636', 'url': ''}],
                                publisher=[{'email': '','identifier': '','name': '','type': '','uri': 'https://opal.health-ri.nl/pub', 'url': ''}],
                                temporal_start='2020-01-01', temporal_end='2025-12-31')
        assert actual_dataset == expected_dataset

    def test_fdp_record_converter_catalog_dict(self):
        fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
        data = Graph().parse(Path(TEST_DATA_DIRECTORY, "fdp_catalog.ttl")).serialize()
        actual = fdp_record_to_package.record_to_package(
            guid="catalog=https://fair.healthinformationportal.eu/catalog/1c75c2c9-d2cc-44cb-aaa8-cf8c11515c8d",
            record=data)

        expected = {
            "uri": "https://fair.healthinformationportal.eu/catalog/1c75c2c9-d2cc-44cb-aaa8-cf8c11515c8d",
            "access_rights": "https://fair.healthinformationportal.eu/catalog/"
                             "1c75c2c9-d2cc-44cb-aaa8-cf8c11515c8d#accessRights",
            "conforms_to": ["https://fair.healthinformationportal.eu/profile/"
                            "a0949e72-4466-4d53-8900-9436d1049a4b"],
            "extras": [],
            "has_version": ["1.0"],
            "issued": '2023-10-06T10:12:55.614000+00:00',
            "language": ["http://id.loc.gov/vocabulary/iso639-1/en"],
            "license_id": "",
            "modified": '2023-10-06T10:12:55.614000+00:00',
            'publisher': [
                {
                    'email': '',
                    'identifier': '',
                    "name": "Automatic",
                    'type': '',
                    'uri': '',
                    'url': '',
                },
            ],

            "resources": [],
            "tags": [],
            "title": "Slovenia National Node"
        }

        assert actual == expected
