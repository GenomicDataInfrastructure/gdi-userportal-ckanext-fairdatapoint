# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from ckanext.dcat.processors import RDFParser, RDFParserException
from ckanext.fairdatapoint.harvesters.domain.identifier import Identifier
from ckanext.fairdatapoint.processors import FairDataPointRDFParser

log = logging.getLogger(__name__)


class FairDataPointRecordToPackageConverter:

    def __init__(self, profile: str):
        self.profile = profile

    def record_to_package(self, guid: str, record: str):
        parser = FairDataPointRDFParser(profiles=[self.profile])

        try:
            parser.parse(record, _format="ttl")

            identifier = Identifier(guid)
            if identifier.get_id_type() == "catalog":
                for catalog in parser.catalogs():
                    return catalog
            else:
                for dataset in parser.datasets():
                    return dataset
        except RDFParserException as e:
            raise Exception(
                "Error parsing the RDF content [{0}]: {1}".format(record, e)
            )
