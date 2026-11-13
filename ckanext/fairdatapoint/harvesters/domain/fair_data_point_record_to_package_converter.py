# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from typing import Any, Dict, Optional, Sequence, Union

from ckanext.dcat.processors import RDFParserException
from ckanext.fairdatapoint.harvesters.domain.identifier import Identifier
from ckanext.fairdatapoint.processors import FairDataPointRDFParser

log = logging.getLogger(__name__)


class FairDataPointRecordToPackageConverter:
    def __init__(self, profile: Union[str, Sequence[str]]):
        # Space-separated RDF profile names (e.g. "fairdatapoint_dcat_ap euro_dcat_ap_nl", the
        # `ckanext.dcat.rdf.profiles` convention), or a list of them for the chain of a metadata profile.
        self.profile = profile

    def record_to_package(
        self, guid: str, record: str, series_mapping=None
    ) -> Optional[Dict[str, Any]]:
        chain = self.profile.split() if isinstance(self.profile, str) else list(self.profile)
        parser = FairDataPointRDFParser(profiles=chain)

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
                return None

            return items[0]  # Assuming single item per record
        except RDFParserException as e:
            raise Exception(f"Error parsing the RDF content [{record}]: {e}") from e
