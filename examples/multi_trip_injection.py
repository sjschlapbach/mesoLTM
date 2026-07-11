# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Demo: injecting the *same* vehicle several times to track multiple journeys.

When you drive the model step by step (``Simulation.start`` / ``step``) and inject
vehicles by hand (``Simulation.inject``), the same ``Vehicle`` object can be
re-injected once it has completed a trip, to send it on another one. Every trip is
recorded as a separate **journey** on ``vehicle.journeys`` — the single source of
truth for a vehicle's completed trips — so a re-injected vehicle produces one trip
record per journey, exactly as a static demand profile would produce one vehicle per
trip. Trip metrics (``collect_trips``) read those journey records uniformly.

The network is a small relay ``A -> B -> C`` in which ``B`` is **both** a
destination and an origin, so a vehicle can arrive at ``B`` (journey 1) and be
re-injected there for ``B -> C`` (journey 2), re-entering the network at the very
node where it left it. Two guardrails protect re-injection and are demonstrated at
the end: a vehicle that is still moving cannot be re-injected, and (by default) it
must re-enter at the real node where it last left.

Run: ``python examples/multi_trip_injection.py``
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import OUTPUT_DIR  # noqa: E402

from mesoltm import Network, Vehicle  # noqa: E402
from mesoltm.metrics import collect_trips, write_trips_csv  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem
DT = 1.0
TOTAL_TIME = 200.0


def build_network() -> tuple[Network, int, int]:
    """Relay A -> B -> C with B acting as both a destination and an origin."""
    net = Network(default_fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15})
    for node, x in (("A", 0.0), ("B", 1.0), ("C", 2.0)):
        net.add_node(node, pos=(x, 0.0))
    l_ab = net.add_link("A", "B", length=300.0)
    l_bc = net.add_link("B", "C", length=300.0)
    net.set_origin("A")  # trips start here (journey 1)
    net.set_origin("B")  # ...and are re-injected here (journey 2)
    net.set_destination("B")  # journey 1 ends here
    net.set_destination("C")  # journey 2 ends here
    return net, l_ab, l_bc


def run_until_idle(sim, vehicle) -> None:
    """Step the simulation until ``vehicle`` finishes its current journey."""
    while sim.current_step < sim.total_steps and vehicle.active:
        sim.step()


def main() -> None:
    """Send one vehicle on two consecutive journeys and report per-journey metrics."""
    net, l_ab, l_bc = build_network()
    # injection_budget counts every injection, including the re-injection (2 here).
    sim = net.compile(time_step=DT, total_time=TOTAL_TIME, injection_budget=2)
    sim.start()

    # Journey 1: inject at A, bound for B, and run until it arrives.
    vehicle = Vehicle(vehicle_id=0, origin="A", destination="B", route=[l_ab])
    sim.inject("A", vehicle)
    run_until_idle(sim, vehicle)
    print(f"Journey 1 done: vehicle arrived at B at step {vehicle.end}.")

    # Journey 2: the vehicle is idle and sitting (conceptually) at B, so re-inject it
    # there for B -> C. Set the new trip's real links on the vehicle first; the
    # previous journey stays safe in vehicle.journeys.
    vehicle.origin, vehicle.destination, vehicle.route = "B", "C", [l_bc]
    sim.inject("B", vehicle)
    while sim.current_step < sim.total_steps:
        sim.step()
    print(f"Journey 2 done: vehicle arrived at C at step {vehicle.end}.")

    # One vehicle, two journeys — all tracked on the single source of truth.
    print(f"\nvehicle.journeys holds {len(vehicle.journeys)} completed journeys.")
    print("Per-journey trip records (collect_trips):")
    for rec in collect_trips(sim):
        print(
            f"  vehicle {rec['vehicle_id']} journey {rec['journey_index']}: "
            f"{rec['origin']} -> {rec['destination']}  route={rec['route']}  "
            f"travel_time={rec['travel_time']:.0f}s "
            f"(access {rec['access_time']:.0f}s + network {rec['network_time']:.0f}s)"
        )

    out_dir = OUTPUT_DIR / SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = write_trips_csv(
        collect_trips(sim), str(out_dir / "multi_trip_trips.csv")
    )
    print("\nPer-journey trip CSV saved to", csv_path)

    _demonstrate_guardrails()


def _demonstrate_guardrails() -> None:
    """Show the two re-injection guardrails raising as designed."""
    net, l_ab, _l_bc = build_network()
    sim = net.compile(time_step=DT, total_time=TOTAL_TIME, injection_budget=5)
    sim.start()

    print("\nGuardrails:")
    vehicle = Vehicle(vehicle_id=1, origin="A", destination="B", route=[l_ab])
    sim.inject("A", vehicle)
    sim.step()  # vehicle is now active (moving), not yet arrived

    # (1) Cannot re-inject a vehicle that is still moving through the network.
    try:
        sim.inject("A", vehicle)
    except RuntimeError as exc:
        print("  still-active re-injection rejected:", str(exc).split(".")[0] + ".")

    # Let it finish journey 1 (arrives at B).
    run_until_idle(sim, vehicle)

    # (2) By default it must re-enter where it left (B); re-entering at A is rejected.
    vehicle.route = [l_ab]
    try:
        sim.inject("A", vehicle)
    except ValueError as exc:
        print("  wrong-node re-injection rejected:", str(exc).split(".")[0] + ".")


if __name__ == "__main__":
    main()
