# SPDX-FileCopyrightText: 2024 Stichting Health-RI
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from ckan.plugins import toolkit


def get_harvester_setting(harvest_config_dict: dict, config_name: str, default_value):
    """This function queries a harvester setting using a global setting with per-harvester override

    Parameters
    ----------
    harvest_config_dict : dict
        Harvester configuration dictionary, usually converted from a JSON
    config_name : str
        Name of the configuraiton setting
    default_value
        Default value of the setting, if not defined elsehwere

    Returns
    -------
        Harvester setting as found first in local settings, then globally, then default
    """
    if config_name in harvest_config_dict:
        harvester_setting = toolkit.asbool(harvest_config_dict[config_name])
    else:
        harvester_setting = toolkit.asbool(
            toolkit.config.get(f"ckanext.fairdatapoint.{config_name}", default_value)
        )
    return harvester_setting
