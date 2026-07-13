# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for NetworkState.peek_flows: the read-only node-flow prediction query."""

from __future__ import annotations

import pytest

from ..core.simulation import Simulation
from ..core.vehicle import Vehicle
from ..metrics.trips import collect_trips
from ..network.network import Network
from ..network.state import NetworkState
from ..plugins.plugin import FunctionPlugin


def _vehicles(routes: list[list[int]], start: int = 1) -> list[Vehicle]:
    """One vehicle per route, all departing immediately, ids start, start+1, ...

    Each vehicle gets its own copy of the route: the simulation mutates
    ``vehicle.route`` in place (connector attachment), so sharing one list
    between vehicles would corrupt their plans. Give each origin its own id
    range — the tests match arrivals by vehicle id.
    """
    return [
        Vehicle(vehicle_id=i, scheduled_departure=0.0, route=list(route))
        for i, route in enumerate(routes, start=start)
    ]


def _general_junction() -> tuple[Network, dict]:
    """A1/A2 -> M -> B/C (2-in x 2-out, a ``GeneralNodeModel``), demand skewed
    onto the B exit so vehicles queue at M and demand outstrips the node flow."""
    net = Network()
    ids = {
        "a1_m": net.add_link("A1", "M", length=300.0),
        "a2_m": net.add_link("A2", "M", length=300.0),
        "m_b": net.add_link("M", "B", length=300.0),
        "m_c": net.add_link("M", "C", length=300.0),
    }
    net.set_destination("B")
    net.set_destination("C")
    for start, (origin, approach) in enumerate((("A1", "a1_m"), ("A2", "a2_m"))):
        # 6 vehicles to B and 2 to C per approach; the B movement saturates.
        routes = [[ids[approach], ids["m_b"]]] * 6 + [[ids[approach], ids["m_c"]]] * 2
        net.set_origin(origin, vehicles=_vehicles(routes, start=1 + 100 * start))
    return net, ids


def _drive_and_compare(sim: Simulation, node, out_ids: list[int]) -> int:
    """Step through the run asserting peek_flows == the realized arrivals.

    Before every step the prediction for ``node`` is recorded; after the step the
    vehicles that newly appeared on each outbound link must match it exactly
    (same ids, same order). Returns the number of steps on which the movement
    demand exceeded the predicted flow (i.e. the supply limit actually bit).
    """
    state = sim.network_state
    assert state is not None
    sim.start()

    excess_steps = 0
    while sim.current_step < sim.total_steps:
        peek = state.peek_flows(node)
        predicted = {out: [v.vehicle.vehicle_id for v in peek[out]] for out in out_ids}
        demand = sum(len(state.movement_demand(node, out)) for out in out_ids)
        if demand > sum(len(p) for p in predicted.values()):
            excess_steps += 1

        before = {
            out: {v.vehicle_id for v in state.vehicles_on(out)} for out in out_ids
        }
        sim.step()

        for out in out_ids:
            arrived = [
                v.vehicle_id
                for v in state.vehicles_on(out)
                if v.vehicle_id not in before[out]
            ]
            assert arrived == predicted[out]

    return excess_steps


def test_predicts_realized_flows_on_a_general_node():
    """On a congested 2x2 junction the peek equals the realized flows every step."""
    net, ids = _general_junction()
    sim = net.compile(time_step=1.0, total_time=200.0)

    excess_steps = _drive_and_compare(sim, "M", [ids["m_b"], ids["m_c"]])

    # The fixture congests the node: on some steps more vehicles demanded the
    # movements than the peek (correctly) predicted to cross.
    assert excess_steps > 0
    assert len(collect_trips(sim)) == 16  # everyone still arrives


def test_predicts_realized_flows_on_a_one_to_one():
    """The peek also replays a OneToOneNode (one real link in, one out)."""
    net = Network()
    ids = {
        "a_n": net.add_link("A", "N", length=300.0),
        "n_b": net.add_link("N", "B", length=300.0),
    }
    net.set_destination("B")
    net.set_origin("A", vehicles=_vehicles([[ids["a_n"], ids["n_b"]]] * 6))
    sim = net.compile(time_step=1.0, total_time=200.0)

    _drive_and_compare(sim, "N", [ids["n_b"]])


def test_predicts_realized_flows_on_a_merge():
    """On an N->1 merge the peek matches the round-robin priority walk each step."""
    net = Network()
    ids = {
        "a1_m": net.add_link("A1", "M", length=300.0),
        "a2_m": net.add_link("A2", "M", length=300.0),
        "m_b": net.add_link("M", "B", length=300.0),
    }
    net.set_destination("B")
    for start, (origin, approach) in enumerate((("A1", "a1_m"), ("A2", "a2_m"))):
        net.set_origin(
            origin,
            vehicles=_vehicles(
                [[ids[approach], ids["m_b"]]] * 8, start=1 + 100 * start
            ),
        )
    sim = net.compile(time_step=1.0, total_time=200.0)

    excess_steps = _drive_and_compare(sim, "M", [ids["m_b"]])

    # Two approaches merge into one exit of equal capacity, so demand piles up
    # (this is what exercises the persistent priority cursor across steps).
    assert excess_steps > 0


def test_diverge_front_blocking_is_reproduced():
    """A blocked front vehicle blocks the whole diverge — in the peek too."""
    net = Network()
    ids = {
        "a_m": net.add_link("A", "M", length=300.0),
        # Starve the B exit so the front vehicle regularly has to wait.
        "m_b": net.add_link("M", "B", length=300.0, rho_jam=0.0375),
        "m_c": net.add_link("M", "C", length=300.0),
    }
    net.set_destination("B")
    net.set_destination("C")
    # Alternate B/C so a blocked to-B vehicle holds back a to-C follower.
    routes = [
        [ids["a_m"], ids["m_b"]] if i % 2 == 0 else [ids["a_m"], ids["m_c"]]
        for i in range(10)
    ]
    net.set_origin("A", vehicles=_vehicles(routes))
    sim = net.compile(time_step=1.0, total_time=300.0)

    state = sim.network_state
    assert state is not None
    sim.start()

    front_blocked_steps = 0
    while sim.current_step < sim.total_steps:
        peek = state.peek_flows("M")
        predicted_c = len(peek[ids["m_c"]])
        demand_c = len(state.movement_demand("M", ids["m_c"]))
        if predicted_c == 0 and not peek[ids["m_b"]] and demand_c > 0:
            # Somebody wants C, C has room, but the blocked front vehicle
            # (headed for the starved B) holds the whole approach back.
            front_blocked_steps += 1
        before = {v.vehicle_id for v in state.vehicles_on(ids["m_c"])}
        sim.step()
        arrived_c = [
            v.vehicle_id
            for v in state.vehicles_on(ids["m_c"])
            if v.vehicle_id not in before
        ]
        assert len(arrived_c) == predicted_c

    assert front_blocked_steps > 0


def test_supply_overrides_cap_and_relax_the_replay():
    """Overriding an outbound supply reshapes the prediction, and only it."""
    net, ids = _general_junction()
    sim = net.compile(time_step=1.0, total_time=200.0)
    state = sim.network_state
    assert state is not None
    sim.start()

    saw_flow = False
    saw_relaxed = False
    while sim.current_step < sim.total_steps:
        base = state.peek_flows("M")
        capped = state.peek_flows("M", supply_overrides={ids["m_b"]: 0})
        relaxed = state.peek_flows("M", supply_overrides={ids["m_b"]: 100})

        # A zero supply blocks the movement entirely in the replay.
        assert capped[ids["m_b"]] == []
        # A relaxed supply can only admit more, and never more than the demand.
        assert len(relaxed[ids["m_b"]]) >= len(base[ids["m_b"]])
        assert len(relaxed[ids["m_b"]]) <= len(state.movement_demand("M", ids["m_b"]))

        saw_flow = saw_flow or bool(base[ids["m_b"]])
        saw_relaxed = saw_relaxed or (len(relaxed[ids["m_b"]]) > len(base[ids["m_b"]]))
        sim.step()

    assert saw_flow  # the movement was actually exercised...
    assert saw_relaxed  # ...and the real supply constrained it at least once


def test_reroute_after_peek_is_honoured():
    """A route changed after a peek is what the flow phase actually executes.

    The peek leaves no residue in the model: the demand/supply scalars it
    refreshes are recomputed by the simulation's own demand phase (which runs
    after the plugins), and the per-movement split is resolved from the routes
    as they are at flow time. So a plugin can peek, reroute a predicted
    crosser, and the vehicle crosses onto its NEW link that very step.
    """
    net = Network()
    ids = {
        "a_m": net.add_link("A", "M", length=300.0),
        "m_b": net.add_link("M", "B", length=300.0),
        "m_c": net.add_link("M", "C", length=300.0),
    }
    net.set_destination("B")
    net.set_destination("C")
    net.set_origin("A", vehicles=_vehicles([[ids["a_m"], ids["m_b"]]]))

    rerouted_steps: list[int] = []

    def probe(_t: int, state: NetworkState) -> None:
        # The moment the vehicle is predicted to cross toward B, send it to C.
        for view in state.peek_flows("M")[ids["m_b"]]:
            view.vehicle.destination = "C"
            state.set_route(view.vehicle, [view.link_id, ids["m_c"]])
            rerouted_steps.append(state.step)

    sim = net.compile(time_step=1.0, total_time=200.0, plugins=[FunctionPlugin(probe)])
    sim.run(progress=False)
    state = sim.network_state
    assert state is not None

    assert len(rerouted_steps) == 1  # predicted exactly once, then rerouted
    # The vehicle never touched B's link and crossed onto C's instead — the
    # flow phase honoured the post-peek route without any manual refresh.
    assert state.cumulative_inflow(ids["m_b"]) == 0
    assert state.cumulative_inflow(ids["m_c"]) == 1


def test_query_does_not_alter_subsequent_flows():
    """Calling peek_flows every step is pure: trips stay byte-identical."""
    net_a, _ = _general_junction()
    baseline = collect_trips(net_a.compile(time_step=1.0, total_time=200.0).run())

    net_b, ids = _general_junction()

    def probe(_t: int, state: NetworkState) -> None:
        state.peek_flows("M")
        state.peek_flows("M", supply_overrides={ids["m_b"]: 0})

    queried = collect_trips(
        net_b.compile(
            time_step=1.0, total_time=200.0, plugins=[FunctionPlugin(probe)]
        ).run()
    )

    assert queried == baseline


def test_unknown_node_warns_and_returns_empty():
    """A node with no through-junction model yields no prediction (and warns)."""
    net, _ = _general_junction()
    sim = net.compile(time_step=1.0, total_time=50.0)
    assert sim.network_state is not None  # attached by compile()
    with pytest.warns(RuntimeWarning):
        assert not sim.network_state.peek_flows("Z")
