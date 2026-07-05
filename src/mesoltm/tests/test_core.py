# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Unit tests for the core link, nodes and demand generation."""

from __future__ import annotations

import math

import pytest

from ..core.link import Link
from ..core.nodes.destination_node import DestinationNode
from ..core.nodes.merge_node import MergeNode
from ..core.nodes.one_to_one_node import OneToOneNode
from ..core.nodes.origin_node import OriginNode
from ..core.simulation import Simulation
from ..core.vehicle import Vehicle
from ..demand.demand import vehicles_from_demand_profile


def test_link_start_derives_capacity_and_lags():
    """start() must derive capacity and the T1/T2 wave lags correctly."""
    link = Link(link_id=1, length=300, v_f=30.0, w=6.0, rho_jam=0.2)
    link.start(time_step=1.0, total_time=100.0)
    assert link.capacity == 0.2 * 30.0 * 6.0 / (30.0 + 6.0)
    assert link.T1 == max(1, int(300 / (30.0 * 1.0)))
    assert link.T2 == max(1, int(300 / (6.0 * 1.0)))
    assert len(link.cumulative_inflows) == 101


def test_cfl_condition_rejects_too_short_link():
    """start() raises when max(v_f, w) * dt exceeds the link length (paper §3.3)."""
    # v_f * dt = 30 m > length 20 m: the free-flow wave crosses in under one step.
    link = Link(link_id=1, length=20, v_f=30.0, w=6.0, rho_jam=0.2)
    with pytest.raises(ValueError, match="CFL"):
        link.start(time_step=1.0, total_time=10.0)


def test_cfl_condition_allows_one_step_boundary():
    """A link the fastest wave crosses in exactly one step is accepted (T1 == 1)."""
    link = Link(link_id=2, length=30, v_f=30.0, w=6.0, rho_jam=0.2)
    link.start(time_step=1.0, total_time=10.0)
    assert link.T1 == 1


def test_link_demand_zero_before_free_flow_time():
    """A link cannot supply demand before its free-flow travel time elapses."""
    link = Link(link_id=1, length=300, v_f=30.0, w=6.0, rho_jam=0.2)
    link.start(1.0, 100.0)
    link.compute_demand_and_supplies(0)
    assert link.get_demand() == 0


def test_vehicle_next_link_follows_route():
    """A vehicle resolves its next link from its route."""
    v = Vehicle(vehicle_id=0, route=[1, 2, 3])
    assert v.next_link(1) == 2
    assert v.next_link(3) is None


def test_vehicle_props_default_and_mutable():
    """props default to an empty dict, are copied at init, and can be updated."""
    v = Vehicle(vehicle_id=0)
    assert isinstance(v.props, dict) and not v.props  # default empty, never None

    source = {"cls": "van"}
    v2 = Vehicle(vehicle_id=1, props=source)
    assert v2.props == {"cls": "van"}
    v2.props["cls"] = "truck"  # freely updatable later / in a different context
    v2.props["value_of_time"] = 12.5
    assert v2.props == {"cls": "truck", "value_of_time": 12.5}
    assert source == {"cls": "van"}  # init copied, so the caller's dict is untouched


def test_demand_profile_vehicle_count_and_routes():
    """Demand expansion yields the expected number of vehicles and route split."""
    trips = vehicles_from_demand_profile(
        [1.0], 10.0, route_integer_share={(1, 2): 1, (1, 3): 1}
    )
    assert len(trips) == 10
    r12 = sum(1 for t in trips if t.route == [1, 2])
    r13 = sum(1 for t in trips if t.route == [1, 3])
    assert r12 == r13 == 5


def test_single_link_conserves_vehicles():
    """A single origin->link->destination run discharges every vehicle."""
    link = Link(link_id=1, length=150, v_f=30.0, w=6.0, rho_jam=0.2)
    trips = vehicles_from_demand_profile([0.2], 100.0, route=[1])
    nodes = [
        OriginNode(node_id=1, link=link, demand_trips=trips),
        DestinationNode(node_id=2, link=link),
    ]
    # Horizon padded beyond the last departure so every vehicle can clear the link.
    Simulation(links=[link], nodes=nodes, time_step=1.0, total_time=150.0).run()
    assert link.cumulative_outflows[-1] == len(trips)


def test_merge_priority_favours_higher_weight():
    """An unbalanced priority vector must send more flow from the favoured link."""
    l1 = Link(link_id=1, length=150, v_f=30.0, w=6.0, rho_jam=0.2)
    l2 = Link(link_id=2, length=150, v_f=30.0, w=6.0, rho_jam=0.2)
    ld = Link(link_id=3, length=150, v_f=30.0, w=6.0, rho_jam=0.05)  # tight bottleneck
    trips1 = vehicles_from_demand_profile([1.0], 120.0, route=[1, 3])
    trips2 = vehicles_from_demand_profile([1.0], 120.0, route=[2, 3])
    nodes = [
        OriginNode(node_id=1, link=l1, demand_trips=trips1),
        OriginNode(node_id=2, link=l2, demand_trips=trips2),
        MergeNode(
            node_id=3,
            outbound_link=ld,
            inbound_links=[l1, l2],
            priority_vector=[0, 0, 0, 1],
        ),  # 3:1 in favour of link 1
        DestinationNode(node_id=4, link=ld),
    ]
    Simulation(links=[l1, l2, ld], nodes=nodes, time_step=1.0, total_time=120.0).run()
    assert l1.cumulative_outflows[-1] > l2.cumulative_outflows[-1]


def test_one_to_one_lane_drop_bounded_congestion():
    """Downstream lane drop must not discharge more than it can (capacity bound)."""
    up = Link(link_id=1, length=150, v_f=30.0, w=6.0, rho_jam=0.2)
    down = Link(link_id=2, length=150, v_f=30.0, w=6.0, rho_jam=0.1)
    trips = vehicles_from_demand_profile([1.0, 0.2, 0.2], 150.0, route=[1, 2])
    nodes = [
        OriginNode(node_id=1, link=up, demand_trips=trips),
        OneToOneNode(node_id=2, inbound_link=up, outbound_link=down),
        DestinationNode(node_id=3, link=down),
    ]
    Simulation(links=[up, down], nodes=nodes, time_step=1.0, total_time=150.0).run()
    cap_down = down.capacity
    # Peak discharge rate over any second cannot exceed the downstream capacity.
    max_rate = max(
        down.cumulative_outflows[t + 1] - down.cumulative_outflows[t]
        for t in range(len(down.cumulative_outflows) - 1)
    )
    assert max_rate <= math.ceil(cap_down) + 1
