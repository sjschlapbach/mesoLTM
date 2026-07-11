# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Tests for the Network builder, connectors, grids and parallel links."""

from __future__ import annotations

import pytest

from ..core.nodes.merge_node import MergeNode
from ..core.vehicle import Vehicle
from ..network.builders import (
    grid_network,
    network_from_dict,
    network_to_dict,
)
from ..network.network import Network


def _od_vehicles(origin, destination, n, route=None):
    """Build ``n`` vehicles (origin to destination) with an optional route."""
    return [
        Vehicle(
            vehicle_id=k,
            scheduled_departure=float(k),
            origin=origin,
            destination=destination,
            route=list(route) if route else None,
        )
        for k in range(n)
    ]


def test_connector_origin_and_destination_all_arrive():
    """A junction origin/destination routes vehicles through auto-connectors."""
    net = Network(default_fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15})
    lab = net.add_link("A", "B", length=200)
    lbd = net.add_link("B", "D", length=200)
    lac = net.add_link("A", "C", length=200)
    lcd = net.add_link("C", "D", length=200)
    vehicles = []
    for k in range(40):
        route = [lab, lbd] if k % 2 == 0 else [lac, lcd]
        vehicles.append(
            Vehicle(
                vehicle_id=k,
                scheduled_departure=float(k),
                route=route,
                origin="A",
                destination="D",
            )
        )
    net.set_origin("A", vehicles=vehicles)
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=200.0)
    sim.run()
    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
    assert arrived == 40


def test_compile_is_one_shot():
    """A second compile is rejected (it would re-splice vehicle routes)."""
    net = Network()
    lid = net.add_link("A", "B", length=200)
    net.set_origin(
        "A", vehicles=[Vehicle(vehicle_id=0, scheduled_departure=0.0, route=[lid])]
    )
    net.set_destination("B")
    net.compile(time_step=1.0, total_time=10.0)
    with pytest.raises(RuntimeError, match="once"):
        net.compile(time_step=1.0, total_time=10.0)


def test_duplicate_explicit_link_id_rejected():
    """Reusing an explicit link_id must not silently overwrite the first link."""
    net = Network()
    net.add_link("A", "B", length=200, link_id=7)
    with pytest.raises(ValueError, match="already used"):
        net.add_link("B", "C", length=200, link_id=7)


def test_node_model_selection():
    """The builder chooses node models by in/out degree."""

    net = Network(default_fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15})
    net.add_link("A", "B", length=200)
    net.add_link("B", "D", length=200)
    net.add_link("A", "C", length=200)
    net.add_link("C", "D", length=200)
    net.set_origin("A", vehicles=[])
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=10.0)
    kinds = {type(n).__name__ for n in sim.nodes}
    assert "DivergeNode" in kinds  # A: 1 connector-in, 2 out
    assert "MergeNode" in kinds  # D: 2 in, 1 connector-out


def test_partial_grid_skips_nodes_and_edges():
    """Custom/partial grids omit the requested nodes and edges."""
    net = grid_network(3, 3, skip_nodes=[(1, 1)], skip_edges=[((0, 0), (0, 1))])
    d = network_to_dict(net)
    node_ids = {n["id"] for n in d["nodes"]}
    assert "(1, 1)" not in node_ids
    # The skipped directed edge must be absent.
    assert not any(
        link["u"] == "(0, 0)" and link["v"] == "(0, 1)" for link in d["links"]
    )


def test_capacity_proportional_priority_vector():
    """A higher-capacity inbound gets more slots in the priority vector."""
    net = Network()
    # Two inbounds into B with different jam densities (=> different capacities).
    net.add_link("A", "B", length=200, v_f=30, w=6, rho_jam=0.2)  # capacity 1.0
    net.add_link("C", "B", length=200, v_f=30, w=6, rho_jam=0.1)  # capacity 0.5
    net.add_link("B", "D", length=200, v_f=30, w=6, rho_jam=0.2)
    net.set_origin("A", vehicles=[])
    net.set_origin("C", vehicles=[])
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=10.0)
    merge = next(n for n in sim.nodes if isinstance(n, MergeNode))
    # The stronger approach (index of A's link) should appear more often.
    counts = {i: merge.priority_vector.count(i) for i in set(merge.priority_vector)}
    assert max(counts.values()) > min(counts.values())


def test_network_dict_round_trip():
    """A network's topology survives a to_dict / from_dict round trip."""
    net = grid_network(2, 2)
    d = network_to_dict(net)
    net2 = network_from_dict(d)
    assert network_to_dict(net2)["links"] == d["links"]
