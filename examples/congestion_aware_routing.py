# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Demo: load-aware rerouting that balances traffic across two parallel routes.

A ``ReroutingPlugin`` steers vehicles using a shortest-path cost that depends on
**both** a link's length and its **current load**:

    link cost = free-flow travel time (grows with length)
              + LOAD_WEIGHT * (vehicles currently on the link)

The network is a simple diamond: a short "upper" route and a longer "lower" route
share the same start (A) and end (D). With an empty network the upper route is
cheaper, so everyone prefers it — but as it fills up, its load term grows until the
longer-but-emptier lower route becomes cheaper, and the plugin diverts the
overflow there. Because a vehicle can only pick a branch before the split, we only
reroute vehicles still on the entry link A->... ; once past A they are committed.

Run: ``python examples/congestion_aware_routing.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import (  # noqa: E402
    Network,
    NetworkState,
    ReroutingPlugin,
    ShortestPathPolicy,
    Vehicle,
)
from mesoltm.visualizations import plot_network  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

DT = 1.0
TOTAL_TIME = 200.0
# Modest branch capacity so a burst of demand cannot all fit on one route.
BRANCH_FD = {"v_f": 15.0, "w": 5.0, "rho_jam": 0.09}
N_VEHICLES = 40
LAST_DEPARTURE = 40.0  # all vehicles depart within this window (a burst)
LOAD_WEIGHT = 4.0  # seconds of extra cost per vehicle already on a link


def build() -> tuple[Network, dict]:
    """Build the diamond O -> A -> {upper | lower} -> D and return named link ids."""
    net = Network(default_fd=BRANCH_FD)  # branch links use BRANCH_FD unless overridden
    # Positions (for the network plot): a diamond with the upper route on top.
    for node, pos in {
        "O": (0, 0),
        "A": (1, 0),
        "U": (2, 1),
        "L": (2, -1),
        "D": (3, 0),
    }.items():
        net.add_node(node, pos=pos)
    ids = {
        # Entry link with ample capacity: the choice happens at A, not here.
        "in": net.add_link("O", "A", length=300.0, rho_jam=0.3),
        # Upper route: two short links (fast when empty).
        "up1": net.add_link("A", "U", length=250.0),
        "up2": net.add_link("U", "D", length=250.0),
        # Lower route: two longer links (slower, but an alternative when upper jams).
        "low1": net.add_link("A", "L", length=450.0),
        "low2": net.add_link("L", "D", length=450.0),
    }
    # A burst of vehicles from O to D, all initially planned via the upper route.
    headway = LAST_DEPARTURE / N_VEHICLES
    vehicles = [
        Vehicle(
            vehicle_id=k,
            start=k * headway,
            origin="O",
            destination="D",
            route=[ids["in"], ids["up1"], ids["up2"]],
        )
        for k in range(N_VEHICLES)
    ]
    net.set_origin("O", vehicles=vehicles)
    net.set_destination("D")
    return net, ids


def main() -> None:
    """Run the load-balancing demo and save a branch-occupancy figure."""
    net, ids = build()

    def cost(link_id: int, state: NetworkState) -> float:
        # Length term (free-flow time) + congestion term (current vehicle count).
        # The typed ``state`` gives fully-typed access to live link quantities.
        return state.free_flow_time(link_id) + LOAD_WEIGHT * state.occupancy(link_id)

    # Plan shortest paths on the load-aware cost, recomputed live (dynamic=True).
    planner = ShortestPathPolicy(cost=cost, dynamic=True)

    def reroute(_t, state, vehicles):
        """Re-plan the cheapest route for vehicles that can still choose a branch."""
        updates = {}
        for view in vehicles:
            # Only vehicles on the entry link can still pick upper vs lower; once on
            # a branch the rest of the path is forced, so re-planning changes nothing.
            if view.link_id != ids["in"]:
                continue

            planned = [ids["in"]] + planner.route(state, "A", view.destination)
            if planned != view.route:
                updates[view.vehicle] = planned

        return updates

    # Default node routing (vehicles follow their route); the plugin edits routes.
    sim = net.compile(
        time_step=DT, total_time=TOTAL_TIME, plugins=[ReroutingPlugin(reroute)]
    )
    state = sim.network_state
    assert state is not None  # set by compile()

    # Record, at each step: how many vehicles sit on each branch's first link, the
    # cumulative number that have entered the network at the origin (inflow on the
    # entry link O->A), and how those entrants were split across the two branches.
    upper_load, lower_load = [], []
    entered, via_upper, via_lower = [], [], []
    sim.start()
    while sim.current_step < sim.total_steps:
        sim.step()
        upper_load.append(state.occupancy(ids["up1"]))
        lower_load.append(state.occupancy(ids["low1"]))
        entered.append(state.cumulative_inflow(ids["in"]))
        via_upper.append(state.cumulative_inflow(ids["up1"]))
        via_lower.append(state.cumulative_inflow(ids["low1"]))

    took_upper = state.cumulative_outflow(ids["up1"], sim.total_steps)
    took_lower = state.cumulative_outflow(ids["low1"], sim.total_steps)
    print(f"Load-aware rerouting of {N_VEHICLES} vehicles:")
    print(f"  upper (short) route: {took_upper:.0f} vehicles")
    print(f"  lower (long)  route: {took_lower:.0f} vehicles")
    print("The overflow the short route could not absorb was sent the long way.")

    matplotlib.use("Agg")
    # Left: the diamond coloured/labelled by total flow — the split across the two
    # routes is visible on the network itself. Middle: branch load over time.
    # Right: cumulative vehicles entering the network at the origin, together with
    # how the rerouting split them across the branches — so the demand driving the
    # rerouting decisions and their effect are visible in the same panel.
    fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))
    plot_network(state, color_by="flow", annotate_links=True, ax=axes[0])

    times = [i * DT for i in range(len(upper_load))]
    axes[1].plot(times, upper_load, label="upper (short) route", color="tab:blue")
    axes[1].plot(times, lower_load, label="lower (long) route", color="tab:orange")
    axes[1].set_xlabel("time (s)")
    axes[1].set_ylabel("vehicles on branch entry link")
    axes[1].set_title("Load-aware rerouting balances the two routes")
    axes[1].legend()

    # The black curve is the total demand loaded into the network; the gap between
    # it and (upper + lower) is vehicles still on the entry link, not yet routed.
    axes[2].plot(times, entered, label="entered network (origin)", color="black", lw=2)
    axes[2].plot(times, via_upper, label="routed via upper", color="tab:blue")
    axes[2].plot(times, via_lower, label="routed via lower", color="tab:orange")
    axes[2].set_xlabel("time (s)")
    axes[2].set_ylabel("cumulative vehicles")
    axes[2].set_title("Origin inflow and its route split")
    axes[2].legend()

    fig.tight_layout()
    print("\nFigure saved to", savefig(fig, "congestion_network_flow", subdir=SUBDIR))


if __name__ == "__main__":
    main()
