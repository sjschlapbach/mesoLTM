# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""mesoltm — mesoscopic (individual-vehicle) Link Transmission Model.

A pip-installable traffic-flow simulator implementing the discrete/mesoscopic LTM
of de Souza, Verbas, Auld & Tampère (SIMPAT 140 (2025) 103088) on general road
networks, with pluggable per-vehicle routing, external simulation plugins (per-step
loop hooks), and visualisations.

The most-used names are re-exported here so ``import mesoltm as m`` gives quick
access to links, node models, the simulation loop, and demand helpers.
"""

from __future__ import annotations

from .plugins import FunctionPlugin, Plugin, ReroutingPlugin
from .core import (
    BaseLink,
    ConnectorLink,
    Link,
    NodeId,
    Simulation,
    Vehicle,
)
from .core.nodes import (
    BaseNode,
    DestinationNode,
    DivergeNode,
    GeneralNodeModel,
    MergeNode,
    OneToOneNode,
    OriginNode,
)
from .demand import vehicles_from_demand_profile
from .metrics import (
    collect_trips,
    free_flow_time,
    summarize_trips,
    trip_record,
    write_trips_csv,
)
from .network import (
    Network,
    NetworkState,
    VehicleView,
    corridor_network,
    grid_network,
    link_capacity,
    network_from_dict,
    network_to_dict,
)
from .recording import (
    AgentSnapshot,
    Frame,
    SimulationHistory,
    WaitingSnapshot,
    capture_frame,
    record_run,
)
from .routing import RoutingPolicy, ShortestPathPolicy, StaticRoutePolicy

__version__ = "1.0.0"

__all__ = [
    "__version__",
    # links
    "BaseLink",
    "Link",
    "ConnectorLink",
    # vehicle / loop
    "Vehicle",
    "Simulation",
    # identifiers
    "NodeId",
    # nodes
    "BaseNode",
    "OneToOneNode",
    "DivergeNode",
    "MergeNode",
    "GeneralNodeModel",
    "OriginNode",
    "DestinationNode",
    # demand / routing
    "vehicles_from_demand_profile",
    # metrics
    "collect_trips",
    "trip_record",
    "free_flow_time",
    "summarize_trips",
    "write_trips_csv",
    "RoutingPolicy",
    "StaticRoutePolicy",
    "ShortestPathPolicy",
    # network
    "Network",
    "NetworkState",
    "VehicleView",
    "link_capacity",
    "corridor_network",
    "grid_network",
    "network_from_dict",
    "network_to_dict",
    # history recording (for animation/video; matplotlib-free)
    "SimulationHistory",
    "Frame",
    "AgentSnapshot",
    "WaitingSnapshot",
    "capture_frame",
    "record_run",
    # plugins (per-step loop hooks)
    "Plugin",
    "FunctionPlugin",
    "ReroutingPlugin",
]
