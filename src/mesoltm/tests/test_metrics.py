# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Tests for per-vehicle travel-time tracking and trip metrics."""

from __future__ import annotations

from ..core.vehicle import Vehicle
from ..metrics import collect_trips, summarize_trips
from ..metrics.trips import trip_record
from ..network.network import Network
from ..routing.shortest_path import ShortestPathPolicy


def test_free_flow_travel_time_matches_wave_lag():
    """An uncongested link's recorded travel time equals its free-flow lag T1."""
    net = Network()
    # length 300 at v_f 15 with dt 1 => T1 = 20 steps => 20 s free-flow travel.
    lid = net.add_link("O", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    net.set_origin("O", vehicles=[Vehicle(vehicle_id=7, start=0.0, route=[lid])])
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=100.0).run()

    trips = collect_trips(sim)
    assert len(trips) == 1
    trip = trips[0]
    assert trip["vehicle_id"] == 7  # associatable by the vehicle's own id
    assert trip["travel_time"] == 20.0  # total = access + network
    assert trip["access_time"] == 0.0  # no origin queue, direct link (no connector)
    assert trip["network_time"] == 20.0
    assert trip["route"] == [lid]  # the real link actually driven
    assert trip["link_travel_times"] == {lid: 20.0}


def test_per_link_times_recorded_for_every_traversed_link():
    """Each link on a multi-link route gets its own recorded travel time."""
    net = Network()
    l1 = net.add_link("O", "A", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    l2 = net.add_link("A", "B", length=150.0, v_f=15.0, w=5.0, rho_jam=0.15)
    l3 = net.add_link("B", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    net.set_origin("O", vehicles=[Vehicle(vehicle_id=0, start=0.0, route=[l1, l2, l3])])
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=100.0).run()

    trip = collect_trips(sim)[0]
    # T1 = length / (v_f * dt): 20, 10, 20 steps respectively.
    assert trip["link_travel_times"] == {l1: 20.0, l2: 10.0, l3: 20.0}
    assert trip["n_links"] == 3
    # Overall network time spans all three free-flow links.
    assert trip["travel_time"] == 50.0


def test_link_times_recorded_across_diverge_and_merge():
    """Diverge/merge nodes still record every real link (they inflow before outflow)."""
    net = Network()
    l_in = net.add_link("O", "A", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    l_main = net.add_link("A", "B", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    l_detour = net.add_link("A", "B", length=600.0, v_f=15.0, w=5.0, rho_jam=0.15)
    l_out = net.add_link("B", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    vehicles = [
        Vehicle(vehicle_id=0, start=0.0, route=[l_in, l_main, l_out]),
        Vehicle(vehicle_id=1, start=0.0, route=[l_in, l_detour, l_out]),
    ]
    net.set_origin("O", vehicles=vehicles)
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=200.0).run()

    trips = {t["vehicle_id"]: t for t in collect_trips(sim)}
    # Free-flow lags: in=20, main=20, detour=40, out=20 steps.
    assert trips[0]["link_travel_times"] == {l_in: 20.0, l_main: 20.0, l_out: 20.0}
    assert trips[1]["link_travel_times"] == {l_in: 20.0, l_detour: 40.0, l_out: 20.0}
    # The detour vehicle takes 20 s longer overall than the main-route vehicle.
    assert trips[1]["travel_time"] == trips[0]["travel_time"] + 20.0


def test_empty_connector_free_flow_lag_excluded_from_travel_time():
    """An empty, unrestricted destination connector is pure free-flow (one step);
    that artificial lag must not inflate travel_time, access_time, or network_time."""
    net = Network()
    for nid in ("a", "b", "c"):
        net.add_node(nid)
    # b is both a destination and a through node (b->c), so it is not a pure
    # single-link endpoint and the builder inserts a destination connector.
    net.add_link("a", "b", length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)
    net.add_link("b", "c", length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)
    net.set_origin(
        "a", vehicles=[Vehicle(vehicle_id=0, origin="a", destination="b", start=0.0)]
    )
    net.set_destination("b")
    sim = net.compile(
        time_step=1.0, total_time=200.0, routing_policy=ShortestPathPolicy(dynamic=True)
    ).run()

    trip = collect_trips(sim)[0]
    # a->b is a 300 m / 30 m/s = 10 s free-flow real link; the destination connector
    # is empty, so its single free-flow step is removed and adds nothing.
    assert trip["network_time"] == 10.0  # real link only
    assert trip["access_time"] == 0.0  # no queue, connector free-flow lag removed
    assert trip["travel_time"] == 10.0
    assert trip["travel_time"] == trip["access_time"] + trip["network_time"]
    assert trip["link_travel_times"] == {1: 10.0}


def test_supply_limited_connector_wait_is_kept_but_free_flow_lag_removed():
    """On a connector, only the one free-flow step is removed; extra time spent
    waiting because downstream supply was the binding constraint stays in
    travel_time (as access). Uses a synthetic trajectory for exact control."""
    dt = 1.0
    v = Vehicle(vehicle_id=0, start=0.0)
    # Source connector held for 3 steps (1 free-flow + 2 supply-limited wait),
    # then a 10-step real link.
    v.trajectory = [
        {"link_id": 900, "entry_step": 0, "exit_step": 3, "is_connector": True},
        {"link_id": 1, "entry_step": 3, "exit_step": 13, "is_connector": False},
    ]
    v.end = 13

    rec = trip_record(v, dt)
    assert rec["network_time"] == 10.0  # the real link only
    # 3 s on the connector minus the 1 s free-flow lag = 2 s of genuine entry wait.
    assert rec["access_time"] == 2.0
    # total 13 s minus the 1 s free-flow lag = 12 s.
    assert rec["travel_time"] == 12.0
    assert rec["travel_time"] == rec["access_time"] + rec["network_time"]


def test_free_flow_origin_and_destination_connectors_add_nothing():
    """A trip crossing empty O/D connectors on both ends reports pure network time."""
    dt = 1.0
    v = Vehicle(vehicle_id=0, start=0.0)
    v.trajectory = [
        {"link_id": 900, "entry_step": 0, "exit_step": 1, "is_connector": True},
        {"link_id": 1, "entry_step": 1, "exit_step": 11, "is_connector": False},
        {"link_id": 901, "entry_step": 11, "exit_step": 12, "is_connector": True},
    ]
    v.end = 12

    rec = trip_record(v, dt)
    assert rec["network_time"] == 10.0
    assert rec["access_time"] == 0.0  # both connectors were free-flow
    assert rec["travel_time"] == 10.0  # 12 total minus 2 free-flow steps


def test_congestion_increases_downstream_travel_time():
    """A bottleneck delays later vehicles, raising travel time above free flow."""
    net = Network()
    l1 = net.add_link("O", "A", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    # Low jam density => low capacity => a binding bottleneck.
    l2 = net.add_link("A", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.03)
    vehicles = [
        Vehicle(vehicle_id=k, start=float(k), route=[l1, l2]) for k in range(20)
    ]
    net.set_origin("O", vehicles=vehicles)
    net.set_destination("D")
    sim = net.compile(time_step=1.0, total_time=600.0).run()

    trips = collect_trips(sim)
    summary = summarize_trips(trips)
    assert summary["n_completed"] >= 1
    # Free-flow time is 40 s; queueing behind the bottleneck must exceed that.
    assert summary["max_travel_time"] > 40.0
    assert summary["mean_travel_time"] >= summary["min_travel_time"]
    # vehicle_id keys are preserved and unique.
    ids = [t["vehicle_id"] for t in trips]
    assert len(ids) == len(set(ids))
