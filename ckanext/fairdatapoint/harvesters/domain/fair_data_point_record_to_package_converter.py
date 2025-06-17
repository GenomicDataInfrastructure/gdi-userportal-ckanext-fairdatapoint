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

    def record_to_package(self, guid: str, record: str, series_mapping=None):
        parser = FairDataPointRDFParser(profiles=[self.profile])

        try:
            parser.parse(record, _format="ttl")

            identifier = Identifier(guid)
            datatype = identifier.get_id_type()
            if datatype == "catalog":
                items = list(parser.catalogs())
            elif datatype == "dataseries":
                items = list(parser.dataset_series())
            else:
                items = list(parser.datasets(series_mapping=series_mapping))

            if not items:
                log.warning("No %s found in RDF", datatype)
                return None  # Returning None instead of False for clarity

            return items[0]  # Assuming single item per record
        except RDFParserException as e:
            raise Exception(
                f"Error parsing the RDF content [{record}]: {e}"
            )
