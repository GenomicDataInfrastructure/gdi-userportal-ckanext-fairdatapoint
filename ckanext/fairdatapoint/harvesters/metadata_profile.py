# SPDX-FileCopyrightText: 2026 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
"""
The RDF profile chain a FAIR data point harvest source parses with.

ckanext-dcat decides which metadata profile a source uses (its ``metadata_profile`` key,
else the deployment's main profile) and which RDF profiles that profile maps to. This module
adds what is specific to a FAIR data point on top: its tag and label clean-up has to run
whichever metadata profile was chosen.
"""
from dataclasses import replace
from typing import Mapping, Optional, Set

from ckanext.dcat.metadata_profiles import (
    ORIGIN_RDF_PROFILE,
    MetadataProfileError,
    ResolvedProfile,
    resolve_source_profile,
)

# Extends the health profile of gdi_current, so it already carries the FAIR data point behaviour.
FDP_RDF_PROFILE = "fairdatapoint_dcat_ap"
# The same behaviour for any other chain; see ckanext.fairdatapoint.profiles.
FDP_ADDITIVE_RDF_PROFILE = "fairdatapoint_additive"


def resolve_fdp_profile(
    source_config: Mapping,
    config: Mapping,
    installed: Optional[Set[str]] = None,
) -> ResolvedProfile:
    """
    The profile a FAIR data point source uses.

    A raw ``profile`` chain is returned as the user wrote it. A chain that comes from a
    metadata profile gets ``fairdatapoint_additive`` appended unless it already contains an
    FDP profile, which is the case for gdi_current, so its chain is unchanged.
    """
    resolved = resolve_source_profile(source_config, config, installed)

    if resolved.origin == ORIGIN_RDF_PROFILE:
        return resolved

    if not resolved.rdf_profiles:
        raise MetadataProfileError(
            "No RDF profiles to parse with: enable a metadata profile "
            "(ckanext.dcat.metadata_profiles), set ckanext.dcat.rdf.profiles, or give "
            "the source a 'profile'"
        )

    chain = list(resolved.rdf_profiles)
    if FDP_RDF_PROFILE in chain or FDP_ADDITIVE_RDF_PROFILE in chain:
        return resolved

    return replace(resolved, rdf_profiles=chain + [FDP_ADDITIVE_RDF_PROFILE])
