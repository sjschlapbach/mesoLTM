# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Tests for shortest-path routing, rerouting plugins and detours."""

from __future__ import annotations

from ..core.vehicle import Vehicle
from ..network.builders import grid_network
from ..network.network import Network
from ..plugins.plugin import FunctionPlugin
from ..routing.shortest_path import ShortestPathPolicy


def test_shortest_path_routes_all_vehicles_on_partial_grid():
    """Shortest-path routing delivers every vehicle on a partial grid."""
    net = grid_network(3, 3, skip_nodes=[(1, 1)], all_nodes_od=True)
    vehicles = [
        Vehicle(vehicle_id=k, start=float(k), origin=(0, 0), destination=(2, 2))
        for k in range(20)
    ]
    net.set_origin((0, 0), vehicles=vehicles)
    sim = net.compile(
        time_step=1.0, total_time=300.0, routing_policy=ShortestPathPolicy(dynamic=True)
    )
    sim.run()
    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
    assert arrived == 20


def test_plugin_closes_link_and_forces_reroute():
    """Closing a link mid-run stops new vehicles from entering it."""
    net = grid_network(3, 3, all_nodes_od=True)
    vehicles = [
        Vehicle(vehicle_id=k, start=float(k), origin=(0, 0), destination=(2, 0))
        for k in range(30)
    ]
    net.set_origin((0, 0), vehicles=vehicles)

    closed: set = set()

    def cost(link_id, state):
        return state.free_flow_time(link_id) + (
            1e6 if state.endpoints(link_id) in closed else 0.0
        )

    def close_link(t, state):
        if t == 5:
            closed.add(((1, 0), (2, 0)))

    sim = net.compile(
        time_step=1.0,
        total_time=400.0,
        routing_policy=ShortestPathPolicy(cost=cost, dynamic=True),
        plugins=[FunctionPlugin(close_link)],
    )
    sim.run()

    state = sim.network_state
    assert state is not None  # set by compile()
    closed_link = state.links_between((1, 0), (2, 0))[0]
    entered_after = state.cumulative_inflow(closed_link, 399) - state.cumulative_inflow(
        closed_link, 20
    )
    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
    assert arrived == 30
    assert entered_after == 0


def test_detour_link_used_only_when_cheaper():
    """A long detour link is avoided unless it is the cheapest remaining option."""
    net = Network()
    net.add_node("A", pos=(0, 0))
    net.add_node("B", pos=(1, 0))
    net.add_node("C", pos=(2, 0))
    fast = net.add_link("A", "B", length=300, v_f=30, w=6, rho_jam=0.2)
    detour = net.add_link("A", "B", length=3000, v_f=30, w=6, rho_jam=0.2)
    net.add_link("B", "C", length=300, v_f=30, w=6, rho_jam=0.2)
    net.set_origin(
        "A",
        vehicles=[
            Vehicle(vehicle_id=k, start=float(k), origin="A", destination="C")
            for k in range(10)
        ],
    )
    net.set_destination("C")
    sim = net.compile(
        time_step=1.0, total_time=200.0, routing_policy=ShortestPathPolicy()
    )
    sim.run()
    state = sim.network_state
    assert state is not None  # set by compile()
    assert state.cumulative_outflow(detour, 199) == 0
    assert state.cumulative_outflow(fast, 199) > 0
