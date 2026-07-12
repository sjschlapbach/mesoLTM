# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for NetworkState.movement_demand: per-movement diverge demand query."""

from __future__ import annotations

import pytest

from ..core.vehicle import Vehicle
from ..metrics.trips import collect_trips
from ..network.network import Network
from ..network.state import NetworkState
from ..plugins.plugin import FunctionPlugin


def _diamond() -> tuple[Network, dict]:
    """A->M, then M diverges to D via B (``m_b``) or via C (``m_c``)."""
    net = Network()
    ids = {
        "a_m": net.add_link("A", "M", length=300.0),
        "m_b": net.add_link("M", "B", length=300.0),
        "b_d": net.add_link("B", "D", length=300.0),
        "m_c": net.add_link("M", "C", length=300.0),
        "c_d": net.add_link("C", "D", length=300.0),
    }
    net.set_destination("D")
    return net, ids


def _reference_demand(state: NetworkState, node, out_link: int) -> list[tuple]:
    """The hand-rolled reference loop from the acceptance criteria (own-route)."""
    demand = []
    for lid in state.in_links(node):
        link = state.links_by_id[lid]
        link.compute_demand_and_supplies(state.step)
        for i in range(link.get_demand()):
            vehicle = link.get_vehicle_from_index(i)
            if vehicle.next_link(lid) == out_link:
                demand.append((vehicle, lid))
    return demand


def test_returns_only_vehicles_routed_onto_the_target_link():
    """Each front vehicle is reported for the movement matching its own route."""
    net, ids = _diamond()
    net.set_origin(
        "A",
        vehicles=[
            Vehicle(
                vehicle_id=1,
                scheduled_departure=0.0,
                route=[ids["a_m"], ids["m_b"], ids["b_d"]],
            ),
            Vehicle(
                vehicle_id=2,
                scheduled_departure=0.0,
                route=[ids["a_m"], ids["m_c"], ids["c_d"]],
            ),
        ],
    )

    demanding_b: set[int] = set()
    demanding_c: set[int] = set()

    def probe(_t: int, state: NetworkState) -> None:
        for v in state.movement_demand("M", ids["m_b"]):
            demanding_b.add(v.vehicle.vehicle_id)
            # The view carries the real inbound link the vehicle is on, so a caller
            # could reroute it with set_route(vehicle, [link_id, ...]).
            assert v.link_id == ids["a_m"]
        for v in state.movement_demand("M", ids["m_c"]):
            demanding_c.add(v.vehicle.vehicle_id)

    sim = net.compile(time_step=1.0, total_time=200.0, plugins=[FunctionPlugin(probe)])
    sim.run(progress=False)

    # Only the via-B vehicle ever demands m_b; only the via-C vehicle demands m_c.
    assert demanding_b == {1}
    assert demanding_c == {2}


def test_equals_the_reference_loop_every_step():
    """With no routing policy the query equals the hand-rolled reference loop."""
    net, ids = _diamond()
    net.set_origin(
        "A",
        vehicles=[
            Vehicle(
                vehicle_id=1,
                scheduled_departure=0.0,
                route=[ids["a_m"], ids["m_b"], ids["b_d"]],
            ),
            Vehicle(
                vehicle_id=2,
                scheduled_departure=0.0,
                route=[ids["a_m"], ids["m_c"], ids["c_d"]],
            ),
        ],
    )

    def probe(_t: int, state: NetworkState) -> None:
        for out_link in (ids["m_b"], ids["m_c"]):
            got = [
                (v.vehicle.vehicle_id, v.link_id)
                for v in state.movement_demand("M", out_link)
            ]
            expected = [
                (v.vehicle_id, lid)
                for v, lid in _reference_demand(state, "M", out_link)
            ]
            assert got == expected

    sim = net.compile(time_step=1.0, total_time=200.0, plugins=[FunctionPlugin(probe)])
    sim.run(progress=False)


class _ForceLink:
    """Routing policy that sends every vehicle onto a fixed outbound link."""

    def __init__(self, next_id: int) -> None:
        self.next_id = next_id

    def next_link(self, vehicle, current_link_id, node, state) -> int:
        """Return the fixed outbound link, ignoring the vehicle's own route."""
        return self.next_id


def test_respects_an_attached_routing_policy():
    """The movement resolves via the node's routing policy, not the vehicle route."""
    net, ids = _diamond()
    # The vehicle's own route plans via B, but the policy forces everyone via C.
    net.set_origin(
        "A",
        vehicles=[
            Vehicle(
                vehicle_id=1,
                scheduled_departure=0.0,
                route=[ids["a_m"], ids["m_b"], ids["b_d"]],
            )
        ],
    )

    toward_b: list[int] = []
    toward_c: list[int] = []

    def probe(_t: int, state: NetworkState) -> None:
        toward_b.append(len(state.movement_demand("M", ids["m_b"])))
        toward_c.append(len(state.movement_demand("M", ids["m_c"])))

    sim = net.compile(
        time_step=1.0,
        total_time=200.0,
        routing_policy=_ForceLink(ids["m_c"]),
        plugins=[FunctionPlugin(probe)],
    )
    sim.run(progress=False)

    # Policy overrides the own-route plan: demand shows toward C, never toward B.
    assert max(toward_b) == 0
    assert max(toward_c) == 1


def test_query_does_not_alter_subsequent_flows():
    """Calling movement_demand is a pure query: trips are byte-identical."""

    def build() -> tuple[Network, dict]:
        net, ids = _diamond()
        net.set_origin(
            "A",
            vehicles=[
                Vehicle(
                    vehicle_id=1,
                    scheduled_departure=0.0,
                    route=[ids["a_m"], ids["m_b"], ids["b_d"]],
                ),
                Vehicle(
                    vehicle_id=2,
                    scheduled_departure=0.0,
                    route=[ids["a_m"], ids["m_c"], ids["c_d"]],
                ),
            ],
        )
        return net, ids

    net_a, _ = build()
    baseline = collect_trips(net_a.compile(time_step=1.0, total_time=200.0).run())

    net_b, ids = build()

    def probe(_t: int, state: NetworkState) -> None:
        state.movement_demand("M", ids["m_b"])
        state.movement_demand("M", ids["m_c"])

    queried = collect_trips(
        net_b.compile(
            time_step=1.0, total_time=200.0, plugins=[FunctionPlugin(probe)]
        ).run()
    )

    assert queried == baseline


def test_unknown_node_returns_empty():
    """A node with no through-junction model yields no movement demand (and warns)."""
    net, ids = _diamond()
    net.set_origin("A", vehicles=[Vehicle(vehicle_id=1, route=[ids["a_m"]])])
    sim = net.compile(time_step=1.0, total_time=50.0)
    assert sim.network_state is not None  # attached by compile()
    with pytest.warns(RuntimeWarning):
        assert not sim.network_state.movement_demand("Z", ids["a_m"])


def test_includes_demand_queued_on_an_origin_connector():
    """Vehicles still on a source connector count toward the movement they plan."""
    # Origin A diverges directly to B (a_b) or C (a_c); A is fed by a source
    # connector, so at some steps the demanding vehicles sit on that connector.
    net = Network()
    ids = {
        "a_b": net.add_link("A", "B", length=300.0),
        "a_c": net.add_link("A", "C", length=300.0),
    }
    net.set_destination("B")
    net.set_destination("C")
    net.set_origin(
        "A",
        vehicles=[
            Vehicle(vehicle_id=1, scheduled_departure=0.0, route=[ids["a_b"]]),
            Vehicle(vehicle_id=2, scheduled_departure=0.0, route=[ids["a_c"]]),
        ],
    )

    demanding_b: set[int] = set()
    seen_on_connector = False

    def probe(_t: int, state: NetworkState) -> None:
        nonlocal seen_on_connector
        for v in state.movement_demand("A", ids["a_b"]):
            demanding_b.add(v.vehicle.vehicle_id)
            # A connector link has no real (u, v) endpoints entry.
            if state.endpoints(v.link_id) is None:
                seen_on_connector = True

    sim = net.compile(time_step=1.0, total_time=100.0, plugins=[FunctionPlugin(probe)])
    sim.run(progress=False)

    assert demanding_b == {1}  # only the via-B vehicle demands a_b
    assert seen_on_connector  # and it was counted while queued on the connector


def test_shown_only_while_on_link_and_after_free_flow_traversal():
    """Step-by-step: a vehicle appears in ``movement_demand`` for the L2->L3 movement
    if and only if it is on L2 and has been there long enough to traverse it at free
    flow (its ``T1`` wave lag). It must be absent while still on the upstream link L1,
    absent during the early steps on L2, and present only once it is ready to cross.

    A single vehicle on a straight line N0->N1->N2->N3 (so nothing else congests it).
    """
    net = Network()
    ids = {
        "l1": net.add_link("N0", "N1", length=45.0, v_f=15.0, w=5.0, rho_jam=0.15),
        "l2": net.add_link("N1", "N2", length=45.0, v_f=15.0, w=5.0, rho_jam=0.15),
        "l3": net.add_link("N2", "N3", length=45.0, v_f=15.0, w=5.0, rho_jam=0.15),
    }
    vehicle = Vehicle(
        vehicle_id=1,
        scheduled_departure=0.0,
        route=[ids["l1"], ids["l2"], ids["l3"]],
    )
    net.set_origin("N0", vehicles=[vehicle])
    net.set_destination("N3")

    sim = net.compile(time_step=1.0, total_time=40.0)
    sim.start()
    state = sim.network_state
    assert state is not None
    # Free-flow traversal of L2 in whole steps (T1 = floor(length / (v_f * dt)) = 3).
    t1_l2 = state.links_by_id[ids["l2"]].T1
    assert t1_l2 > 1  # so there are on-L2 steps *before* the vehicle is ready

    def on_l2() -> bool:
        return any(v is vehicle for v in state.vehicles_on(ids["l2"]))

    def shown() -> bool:
        views = state.movement_demand("N2", ids["l3"])
        return any(v.vehicle is vehicle for v in views)

    on_l2_steps: list[int] = []
    shown_steps: list[int] = []
    while sim.current_step < sim.total_steps:
        t = state.step  # the step about to run (plugin-phase view of it)
        if on_l2():
            on_l2_steps.append(t)
        if shown():
            shown_steps.append(t)
            # A shown vehicle is on the approach link and heading to the movement link.
            assert on_l2()
            assert vehicle.next_link(ids["l2"]) == ids["l3"]
        sim.step()

    assert on_l2_steps, "vehicle never reached link l2"
    entry = on_l2_steps[0]
    # The vehicle only enters the second link after it has fully traversed the first link at free flow.
    assert entry == 4
    # It sits on L2 for exactly its free-flow traversal time (T1 consecutive steps)...
    assert on_l2_steps == list(range(entry, entry + t1_l2))
    # ...and shows as movement demand only on the last of those steps — once it has
    # spent the full free-flow time on L2 and is ready to transfer, never before.
    assert shown_steps == [entry + t1_l2 - 1]
