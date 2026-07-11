# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for the ReroutingPlugin: return-only-the-changed-routes interface."""

from __future__ import annotations

import pytest

from ..core.vehicle import Vehicle
from ..metrics.trips import collect_trips
from ..network.network import Network
from ..plugins.plugin import ReroutingPlugin


def _diamond() -> tuple[Network, dict]:
    """A->M, then M diverges to D via B or via C; both rejoin at D."""
    net = Network()
    ids = {
        "a_m": net.add_link("A", "M", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15),
        "m_b": net.add_link("M", "B", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15),
        "b_d": net.add_link("B", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15),
        "m_c": net.add_link("M", "C", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15),
        "c_d": net.add_link("C", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15),
    }
    net.set_destination("D")
    return net, ids


def test_returned_route_is_applied_and_followed():
    """A vehicle planned via B is rerouted onto the C path and drives it."""
    net, ids = _diamond()
    # Default plan goes via B; the plugin will divert it via C at node M.
    net.set_origin(
        "A",
        vehicles=[Vehicle(vehicle_id=1, route=[ids["a_m"], ids["m_b"], ids["b_d"]])],
    )

    def reroute(_t, _state, vehicles):
        updates = {}
        for view in vehicles:
            # While still on the first link and still planning via B, divert via C.
            if view.link_id == ids["a_m"] and ids["m_b"] in view.route:
                updates[view.vehicle] = [ids["a_m"], ids["m_c"], ids["c_d"]]
        return updates

    sim = net.compile(
        time_step=1.0, total_time=200.0, plugins=[ReroutingPlugin(reroute)]
    )
    sim.run()

    trips = collect_trips(sim)
    assert len(trips) == 1
    assert trips[0]["route"] == [ids["a_m"], ids["m_c"], ids["c_d"]]  # took the C path


def test_omitted_vehicles_keep_their_route():
    """Only vehicles in the returned map change; others are untouched."""
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
                route=[ids["a_m"], ids["m_b"], ids["b_d"]],
            ),
        ],
    )

    def reroute(_t, _state, vehicles):
        # Reroute only vehicle 1; vehicle 2 must keep its via-B plan.
        return {
            v.vehicle: [ids["a_m"], ids["m_c"], ids["c_d"]]
            for v in vehicles
            if v.vehicle.vehicle_id == 1
            and v.link_id == ids["a_m"]
            and ids["m_b"] in v.route
        }

    sim = net.compile(
        time_step=1.0, total_time=200.0, plugins=[ReroutingPlugin(reroute)]
    )
    sim.run()

    routes = {t["vehicle_id"]: t["route"] for t in collect_trips(sim)}
    assert routes[1] == [ids["a_m"], ids["m_c"], ids["c_d"]]  # rerouted via C
    assert routes[2] == [ids["a_m"], ids["m_b"], ids["b_d"]]  # unchanged via B


def test_route_not_starting_at_current_link_is_rejected():
    """set_route guards against a route that would strand the vehicle."""
    net, ids = _diamond()
    net.set_origin(
        "A",
        vehicles=[Vehicle(vehicle_id=1, route=[ids["a_m"], ids["m_b"], ids["b_d"]])],
    )

    def reroute(_t, _state, vehicles):
        # Deliberately return a route that does NOT start at the current link.
        return {v.vehicle: [ids["m_c"], ids["c_d"]] for v in vehicles}

    sim = net.compile(
        time_step=1.0, total_time=50.0, plugins=[ReroutingPlugin(reroute)]
    )
    with pytest.raises(ValueError):
        sim.run()


def test_missing_reroute_implementation_raises():
    """A bare ReroutingPlugin with no callback/override is a usage error."""
    net, _ids = _diamond()
    net.set_origin("A", vehicles=[Vehicle(vehicle_id=1, route=[_ids["a_m"]])])
    sim = net.compile(time_step=1.0, total_time=50.0, plugins=[ReroutingPlugin()])
    with pytest.raises(NotImplementedError):
        sim.run()
