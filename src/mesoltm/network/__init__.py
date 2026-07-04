# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Network construction, read-only state access and convenience builders."""

from .builders import (
    corridor_network,
    grid_network,
    network_from_dict,
    network_to_dict,
)
from .network import Network, link_capacity
from .state import NetworkState, VehicleView

__all__ = [
    "Network",
    "NetworkState",
    "VehicleView",
    "link_capacity",
    "corridor_network",
    "grid_network",
    "network_from_dict",
    "network_to_dict",
]
