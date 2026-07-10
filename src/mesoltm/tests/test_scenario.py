# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Tests for JSON scenario building and the entry-queue behaviour."""

from __future__ import annotations

from ..core.nodes.origin_node import OriginNode
from ..core.vehicle import Vehicle
from ..io.scenario import build_scenario
from ..network.network import Network


def test_build_and_run_scenario_from_dict():
    """A scenario dict compiles and runs, discharging vehicles."""
    data = {
        "time_step": 1.0,
        "total_time": 300.0,
        "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}, {"id": "n4"}],
        "links": [
            {
                "id": 1,
                "u": "n1",
                "v": "n2",
                "length": 300,
                "v_f": 30,
                "w": 6,
                "rho_jam": 0.2,
            },
            {
                "id": 2,
                "u": "n2",
                "v": "n3",
                "length": 600,
                "v_f": 30,
                "w": 6,
                "rho_jam": 0.2,
            },
            {
                "id": 3,
                "u": "n2",
                "v": "n3",
                "length": 300,
                "v_f": 30,
                "w": 6,
                "rho_jam": 0.1,
            },
            {
                "id": 4,
                "u": "n3",
                "v": "n4",
                "length": 300,
                "v_f": 30,
                "w": 6,
                "rho_jam": 0.1,
            },
        ],
        "origins": [
            {
                "node": "n1",
                "demand": {
                    "profile": [0.5, 0.8, 0.2],
                    "route_shares": {"1,2,4": 1, "1,3,4": 2},
                },
            }
        ],
        "destinations": ["n4"],
    }
    sim = build_scenario(data)
    sim.run()
    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
    assert arrived > 0


def test_origin_entry_queue_backpressure():
    """When the network cannot admit demand, vehicles wait in the origin queue."""
    net = Network()
    # Tight downstream bottleneck so the origin cannot inject everyone at once.
    net.add_link("A", "B", length=150, v_f=30, w=6, rho_jam=0.05)
    net.set_origin(
        "A",
        vehicles=[
            Vehicle(vehicle_id=k, start=0.0, origin="A", destination="B")
            for k in range(50)
        ],
    )
    net.set_destination("B")
    sim = net.compile(time_step=1.0, total_time=20.0)
    sim.run()
    origin = next(n for n in sim.nodes if isinstance(n, OriginNode))
    # All depart at t=0 but only a few can enter, so a queue must form.
    assert max(origin.entry_queue) > 0
