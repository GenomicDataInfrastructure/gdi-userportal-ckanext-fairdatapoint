# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from datetime import datetime
from dateutil.tz import tzutc
from pathlib import Path
from rdflib import Graph
from ckanext.fairdatapoint.profiles import validate_tags
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter
)

TEST_DATA_DIRECTORY = Path(Path(__file__).parent.resolve(), "test_data")


@pytest.mark.parametrize("input_tags,expected_tags", [
    ([{"name": "CNS/Brain"}], [{"name": "CNS Brain"}]),
    ([{"name": "COVID-19"}, {"name": "3`-DNA"}], [{"name": "COVID-19"}, {"name": "3 -DNA"}]),
    ([{"name": "something-1.1"}, {"name": "breast cancer"}], [{"name": "something-1.1"}, {"name": "breast cancer"}]),
    ([{"name": "-"}], []),
    ([{"name": "It is a ridiculously long (more 100 chars) text for a tag therefore it should be removed from the "
               "result to prevent CKAN harvester from failing"}], []),
    ([], [])
])
def test_validate_tags(input_tags, expected_tags):
    actual_tags = validate_tags(input_tags)
    assert actual_tags == expected_tags


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
def test_parse_dataset():
    """Dataset with keywords which should be modified"""
    fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
    data = Graph().parse(Path(TEST_DATA_DIRECTORY, "dataset_cbioportal.ttl")).serialize()
    actual = fdp_record_to_package.record_to_package(
        guid="catalog=https://health-ri.sandbox.semlab-leiden.nl/catalog/5c85cb9f-be4a-406c-ab0a-287fa787caa0;"
             "dataset=https://health-ri.sandbox.semlab-leiden.nl/dataset/d9956191-1aff-4181-ac8b-16b829135ed5",
        record=data, series_mapping=None)
    expected = {
        'extras': [],
        'resources': [
            {'name': 'Clinical data for [PUBLIC] Low-Grade Gliomas (UCSF, Science 2014)',
             'description': 'Clinical data for [PUBLIC] Low-Grade Gliomas (UCSF, Science 2014)',
             'access_url': 'https://cbioportal.health-ri.nl/study/clinicalData?id=lgg_ucsf_2014',
             'license': 'http://rdflicense.appspot.com/rdflicense/cc-by-nc-nd3.0',
             'url': 'https://cbioportal.health-ri.nl/study/clinicalData?id=lgg_ucsf_2014',
             'uri': 'https://health-ri.sandbox.semlab-leiden.nl/distribution/931ed9c4-ad23-47ff-b121-2eb428e57423',
             'distribution_ref': 'https://health-ri.sandbox.semlab-leiden.nl/distribution/931ed9c4-ad23-47ff-b121-2eb428e57423'},
            {'name': 'Mutations',
             'description': 'Mutation data from whole exome sequencing of 23 grade II glioma tumor/normal pairs. (MAF)',
             'access_url': 'https://cbioportal.health-ri.nl/study/summary?id=lgg_ucsf_2014',
             'license': 'http://rdflicense.appspot.com/rdflicense/cc-by-nc-nd3.0',
             'url': 'https://cbioportal.health-ri.nl/study/summary?id=lgg_ucsf_2014',
             'uri': 'https://health-ri.sandbox.semlab-leiden.nl/distribution/ad00299f-6efb-42aa-823d-5ff2337f38f7',
             'distribution_ref': 'https://health-ri.sandbox.semlab-leiden.nl/distribution/ad00299f-6efb-42aa-823d-5ff2337f38f7'}
        ],
        'title': '[PUBLIC] Low-Grade Gliomas (UCSF, Science 2014)',
        'notes': 'Whole exome sequencing of 23 grade II glioma tumor/normal pairs.',
        'url': 'https://cbioportal.health-ri.nl/study/summary?id=lgg_ucsf_2014',
        'tags': [{'name': 'CNS Brain'}, {'name': 'Diffuse Glioma'}, {'name': 'Glioma'}],
        'license_id': '',
        'issued': '2019-10-30 23:00:00',
        'modified': '2019-10-30 23:00:00',
        'identifier': 'lgg_ucsf_2014',
        'language': ['http://id.loc.gov/vocabulary/iso639-1/en'],
        'conforms_to': ['https://health-ri.sandbox.semlab-leiden.nl/profile/2f08228e-1789-40f8-84cd-28e3288c3604'],
        'publisher': [
            {'email': '', 'identifier': '', 'name': '', 'type': '', 'uri': 'https://www.health-ri.nl', 'url': ''}],
        'uri': 'https://health-ri.sandbox.semlab-leiden.nl/dataset/d9956191-1aff-4181-ac8b-16b829135ed5',
        'is_referenced_by': ['https://pubmed.ncbi.nlm.nih.gov/24336570']  # Make this a list to match 'actual'
    }

    assert actual == expected
