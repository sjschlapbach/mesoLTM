# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.
#
# The traffic-flow logic in this module is adapted from the abmmeso package by
# Felipe de Souza (AGPL-3.0) and follows the model of:
#   F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, "A mesoscopic
#   link-transmission-model able to track individual vehicles", Simulation
#   Modelling Practice and Theory 140 (2025) 103088.
#   https://doi.org/10.1016/j.simpat.2025.103088

"""Numeric regression test locking fidelity to the reference abmmeso model.

The golden cumulative-count checkpoints below were produced by the original
``abmmeso`` discrete implementation on the introduction diverge-merge network.
Any change that perturbs the core LTM arithmetic will break this test.
"""

from __future__ import annotations

from ..core.link import Link
from ..core.nodes.destination_node import DestinationNode
from ..core.nodes.diverge_node import DivergeNode
from ..core.nodes.merge_node import MergeNode
from ..core.nodes.origin_node import OriginNode
from ..core.simulation import Simulation
from ..demand.demand import vehicles_from_demand_profile

GOLDEN_OUT = {
    1: {0: 0, 100: 45, 200: 95, 300: 158, 400: 206, 500: 254, 600: 298},
    2: {0: 0, 100: 12, 200: 29, 300: 50, 400: 65, 500: 82, 600: 98},
    3: {0: 0, 100: 26, 200: 60, 300: 88, 400: 123, 500: 157, 600: 190},
    4: {0: 0, 100: 33, 200: 83, 300: 134, 400: 183, 500: 233, 600: 284},
}
GOLDEN_IN = {
    1: {0: 0, 100: 50, 200: 100, 300: 180, 400: 238, 500: 280, 600: 300},
    2: {0: 0, 100: 15, 200: 32, 300: 53, 400: 69, 500: 85, 600: 100},
    3: {0: 0, 100: 30, 200: 63, 300: 105, 400: 137, 500: 169, 600: 198},
    4: {0: 0, 100: 38, 200: 89, 300: 138, 400: 188, 500: 239, 600: 288},
}


def _run_diverge_merge():
    """Run the canonical diverge-merge network and return links by id."""
    l1 = Link(link_id=1, length=300, rho_jam=0.2, w=6.0, v_f=30.0)
    l2 = Link(link_id=2, length=600, rho_jam=0.2, w=6.0, v_f=30.0)
    l3 = Link(link_id=3, length=300, rho_jam=0.1, w=6.0, v_f=30.0)
    l4 = Link(link_id=4, length=300, rho_jam=0.1, w=6.0, v_f=30.0)
    trips = vehicles_from_demand_profile(
        [0.5, 0.8, 0.2], 600, route_integer_share={(1, 2, 4): 1, (1, 3, 4): 2}
    )
    nodes = [
        OriginNode(node_id=1, link=l1, demand_trips=trips),
        DivergeNode(node_id=2, inbound_link=l1, outbound_links=[l2, l3]),
        MergeNode(
            node_id=3,
            outbound_link=l4,
            inbound_links=[l2, l3],
            priority_vector=[0, 1, 0, 1, 0, 1],
        ),
        DestinationNode(node_id=4, link=l4),
    ]
    Simulation(
        links=[l1, l2, l3, l4], nodes=nodes, time_step=1.0, total_time=600.0
    ).run()
    return {lk.link_id: lk for lk in (l1, l2, l3, l4)}


def test_matches_abmmeso_golden():
    """Cumulative in/outflows must match the abmmeso golden values exactly."""
    links = _run_diverge_merge()
    for lid, checkpoints in GOLDEN_OUT.items():
        for t, expected in checkpoints.items():
            assert links[lid].cumulative_outflows[t] == expected, (lid, t)
    for lid, checkpoints in GOLDEN_IN.items():
        for t, expected in checkpoints.items():
            assert links[lid].cumulative_inflows[t] == expected, (lid, t)


def test_conservation():
    """No link may discharge more vehicles than have entered it."""
    links = _run_diverge_merge()
    for lk in links.values():
        for cum_in, cum_out in zip(
            lk.cumulative_inflows, lk.cumulative_outflows, strict=True
        ):
            assert cum_out <= cum_in
