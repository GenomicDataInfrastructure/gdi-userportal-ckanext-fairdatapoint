# SPDX-FileCopyrightText: 2023 Civity
# SPDX-FileContributor: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only

import encodings
import logging
from typing import Union

import requests
from rdflib import Graph, URIRef
from rdflib.exceptions import ParserError
from requests.exceptions import ConnectionError, HTTPError, RequestException, Timeout

log = logging.getLogger(__name__)
REQUEST_TIMEOUT = 100 # seconds

class FairDataPoint:
    """Class to connect and get data from FDP"""

    def __init__(self, fdp_end_point: str, request_timeout: int = REQUEST_TIMEOUT):
        self.fdp_end_point = fdp_end_point
        self.request_timeout = request_timeout

    def get_graph(self, path: Union[str, URIRef]) -> Graph:
        """
        Get the graph at `path` from the FDP. Fetches with requests rather than rdflib's URL loader,
        which fails on endpoints whose certificate is not in the bundled trust store.
        """
        graph = Graph()
        data = self._get_data(path)
        if data is None:
            log.warning(
                f"No data was received from FDP {self.fdp_end_point} request {path}"
            )
        else:
            try:
                graph.parse(data=data)
            except ParserError as e:
                log.error(f"Record {data} could not be parsed: {e}")
        return graph

    def _get_data(self, path: Union[str, URIRef]) -> Union[str, None]:
        headers = {"Accept": "text/turtle"}
        try:
            response = requests.request(
                "GET", path, headers=headers, timeout=self.request_timeout
            )
            response.encoding = encodings.utf_8.getregentry().name
            response.raise_for_status()
            return response.text
        except (HTTPError, ConnectionError, Timeout, RequestException) as e:
            log.error(f"FDP query {path} was not successful: {e}")
