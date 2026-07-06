# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for step-driven execution and dynamic vehicle injection.

These cover the framework hooks an external control loop relies on: advancing the
simulation one step at a time (``start`` / ``step``) and injecting vehicles into a
node's demand mid-run (``Simulation.inject``), with the origin/destination
connectors spliced on automatically.
"""

from __future__ import annotations

import warnings

import pytest

from ..core.vehicle import Vehicle
from ..metrics.trips import collect_trips
from ..network.network import Network


def _corridor() -> tuple[Network, int, int]:
    """A two-link corridor O -> M -> D; M is also an (injection-only) origin."""
    net = Network()
    l1 = net.add_link("O", "M", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    l2 = net.add_link("M", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    net.set_origin("O", vehicles=[Vehicle(vehicle_id=1, start=0.0, route=[l1, l2])])
    net.set_origin("M")  # no static demand; used for dynamic injection
    net.set_destination("D")
    return net, l1, l2


def test_stepping_to_end_matches_run():
    """Driving the loop with start()/step() reproduces a batch run() exactly."""
    net_a, _, _ = _corridor()
    sim_a = net_a.compile(time_step=1.0, total_time=120.0).run()

    net_b, _, _ = _corridor()
    sim_b = net_b.compile(time_step=1.0, total_time=120.0)
    sim_b.start()
    while sim_b.current_step < sim_b.total_steps:
        sim_b.step()

    a = {t["vehicle_id"]: t["arrival_time"] for t in collect_trips(sim_a)}
    b = {t["vehicle_id"]: t["arrival_time"] for t in collect_trips(sim_b)}
    assert a == b
    assert sim_b.current_step == sim_b.total_steps


def test_inject_vehicle_reaches_destination_empty_connector_no_access():
    """An injected vehicle is routed to its destination. It crosses an (empty)
    source connector, but that connector's one free-flow step is a modelling
    artifact and is removed, so it contributes no access time here."""
    net, _l1, l2 = _corridor()
    sim = net.compile(time_step=1.0, total_time=200.0, injection_budget=5)
    sim.start()

    while sim.current_step < sim.total_steps:
        if sim.current_step == 5:
            sim.inject(
                "M", Vehicle(vehicle_id=99, origin="M", destination="D", route=[l2])
            )
        sim.step()

    trips = {t["vehicle_id"]: t for t in collect_trips(sim)}
    assert 99 in trips  # injected vehicle completed its trip
    rec = trips[99]
    assert rec["route"] == [l2]  # connectors excluded from the driven route
    assert rec["start_time"] == 5.0  # departure defaulted to the injection step
    # M is a through junction, so injection crosses a source connector, but it is
    # empty/unrestricted: its single free-flow step is removed, so access is zero.
    assert rec["access_time"] == 0.0
    assert rec["network_time"] == 20.0  # 300 m at 15 m/s
    assert rec["travel_time"] == pytest.approx(rec["access_time"] + rec["network_time"])


def test_injection_over_budget_warns():
    """Injecting more vehicles than injection_budget emits a RuntimeWarning that
    explains the over-budget vehicle is queued at its origin, not discarded."""
    net, _l1, l2 = _corridor()
    sim = net.compile(time_step=1.0, total_time=200.0, injection_budget=1)
    sim.start()

    # First injection is within the budget of 1: it must not warn.
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # promote any warning to an error
        sim.inject("M", Vehicle(vehicle_id=10, route=[l2]))

    # Second injection exceeds the budget: it must warn (and still be enqueued).
    with pytest.warns(RuntimeWarning, match="injection_budget"):
        sim.inject("M", Vehicle(vehicle_id=11, route=[l2]))


def test_inject_departure_time_can_be_scheduled():
    """A future ``at_time`` delays release until that departure time is reached."""
    net, _l1, l2 = _corridor()
    sim = net.compile(time_step=1.0, total_time=200.0, injection_budget=5)
    sim.start()
    sim.step()  # now at step 1
    sim.inject("M", Vehicle(vehicle_id=42, route=[l2]), at_time=50.0)
    while sim.current_step < sim.total_steps:
        sim.step()

    rec = {t["vehicle_id"]: t for t in collect_trips(sim)}[42]
    assert rec["start_time"] == 50.0
    assert rec["network_entry_time"] >= 50.0


def test_inject_at_non_origin_raises():
    """Injecting at a node that was never marked an origin fails clearly."""
    net, _l1, l2 = _corridor()
    sim = net.compile(time_step=1.0, total_time=50.0, injection_budget=5).start()
    with pytest.raises(ValueError):
        sim.inject("D", Vehicle(vehicle_id=5, route=[l2]))


def test_step_before_start_and_past_horizon_raise():
    """step() guards against running unstarted or beyond the horizon."""
    net, _l1, _l2 = _corridor()
    sim = net.compile(time_step=1.0, total_time=3.0)
    with pytest.raises(RuntimeError):
        sim.step()  # not started yet
    sim.start()
    for _ in range(sim.total_steps):
        sim.step()
    with pytest.raises(RuntimeError):
        sim.step()  # horizon exhausted
