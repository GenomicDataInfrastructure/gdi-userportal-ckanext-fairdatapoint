# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from datetime import datetime
from dateutil.tz import tzutc
from pathlib import Path
from rdflib import Graph
from ckanext.fairdatapoint.profiles import validate_tags, convert_datetime_string
from ckanext.fairdatapoint.harvesters.domain.fair_data_point_record_to_package_converter import (
    FairDataPointRecordToPackageConverter)


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
        record=data)
    expected = {
        'extras': [
            {'key': 'uri',
             'value': 'https://health-ri.sandbox.semlab-leiden.nl/dataset/d9956191-1aff-4181-ac8b-16b829135ed5'}
        ],
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
        'issued': datetime(2019, 10, 30, 23, 0),
        'modified': datetime(2019, 10, 30, 23, 0),
        'identifier': 'lgg_ucsf_2014',
        'language': ['http://id.loc.gov/vocabulary/iso639-1/en'],
        'conforms_to': ['https://health-ri.sandbox.semlab-leiden.nl/profile/2f08228e-1789-40f8-84cd-28e3288c3604'],
        'publisher_uri': 'https://www.health-ri.nl',
        'is_referenced_by': '["https://pubmed.ncbi.nlm.nih.gov/24336570"]'
    }
    assert actual == expected


@pytest.mark.parametrize("input_timestring,expected_output", [
    ("2023-10-06T10:12:55.614000+00:00",
     datetime(2023, 10, 6, 10, 12, 55, 614000, tzinfo=tzutc())),
    ("2024-02-15 11:16:37+03:00",
     datetime(2024, 2, 15, 8, 16, 37, tzinfo=tzutc())),
    ("2014-09-12T19:34:29Z",
     datetime(2014, 9, 12, 19, 34, 29, tzinfo=tzutc())),
    ("2007-04-05T12:30.512000-02:00",
     datetime(2007, 4, 5, 14, 30, 30, tzinfo=tzutc())),
    ("2007-04-05T12:30-02:00",
     datetime(2007, 4, 5, 14, 30, tzinfo=tzutc())),
    ("November 9, 1999", datetime(1999, 11, 9, 0, 0, 0)),
    ("25-06-2023", datetime(2023, 6, 25)),
    ("2006-09", datetime(2006, 9, datetime.today().day))
])
def test_convert_datetime_string(input_timestring, expected_output):
    actual = convert_datetime_string(input_timestring)
    assert actual == expected_output


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
def test_profile_contact_point_uri():
    fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
    data = Graph().parse(Path(TEST_DATA_DIRECTORY, "contact_point_url.ttl")).serialize()
    actual = fdp_record_to_package.record_to_package(
        guid="https://health-ri.sandbox.semlab-leiden.nl/catalog/e3faf7ad-050c-475f-8ce4-da7e2faa5cd0;"
             "dataset=https://health-ri.sandbox.semlab-leiden.nl/dataset/d7129d28-b72a-437f-8db0-4f0258dd3c25",
        record=data)
    expected = {
        'extras': [
            {'key': 'uri',
             'value': 'https://health-ri.sandbox.semlab-leiden.nl/dataset/d7129d28-b72a-437f-8db0-4f0258dd3c25'}
        ],
        'title': 'Example',
        'notes': 'This is an example description.',
        'contact_uri': 'https://orcid.org/0000-0002-9095-9201',
        'license_id': '',
        'resources': [],
        'tags': []
    }
    assert actual == expected


@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
def test_profile_contact_point_vcard():
    fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
    data = Graph().parse(Path(TEST_DATA_DIRECTORY, "contact_point_vcard.ttl")).serialize()
    actual = fdp_record_to_package.record_to_package(
        guid="https://health-ri.sandbox.semlab-leiden.nl/catalog/e3faf7ad-050c-475f-8ce4-da7e2faa5cd0;"
             "dataset=https://health-ri.sandbox.semlab-leiden.nl/dataset/d7129d28-b72a-437f-8db0-4f0258dd3c25",
        record=data)
    expected = {
        'extras': [
            {'key': 'uri',
             'value': 'https://health-ri.sandbox.semlab-leiden.nl/dataset/d7129d28-b72a-437f-8db0-4f0258dd3c25'}
        ],
        'title': 'Example',
        'notes': 'This is an example description.',
        'contact_uri': 'https://orcid.org/0000-0002-9095-9201',
        'contact_name': 'Marc Bonten',
        'contact_email': 'marc.bonten@example.com',
        'license_id': '',
        'resources': [],
        'tags': []
    }
    assert actual == expected

@pytest.mark.ckan_config("ckan.plugins", "scheming_datasets")
@pytest.mark.usefixtures("with_plugins")
def test_profile_creator():
    fdp_record_to_package = FairDataPointRecordToPackageConverter(profile="fairdatapoint_dcat_ap")
    data = Graph().parse(Path(TEST_DATA_DIRECTORY, "creator_prisma.ttl")).serialize()
    actual = fdp_record_to_package.record_to_package(
        guid="https://fdp.radboudumc.nl/catalog/fa48b19f-f390-4023-872d-f0f0024bfcec;"
             "dataset=http://example.org/dataset/1",
        record=data)
    expected = {
        'extras': [
            {'key': 'uri',
             'value': 'http://example.org/dataset/1'}
        ],
        'title': 'Sample Dataset Title',
        'notes': 'This is a description of the sample dataset.',
        'creator': [
            {
                'creator_identifier': 'https://orcid.org/0000-0002-9095-9201',
                'creator_name': 'Marc Bonten'
            }
        ],
        'license_id': '',
        'resources': [],
        'tags': []
    }
    assert actual == expected
