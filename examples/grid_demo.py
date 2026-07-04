"""Demo: a grid network with any node as origin/destination and shortest-path routing.

Builds a 4x4 grid (with one node removed to show a custom/partial layout), marks
every node as both an origin and a destination, injects several origin-destination
flows, and lets the built-in :class:`ShortestPathPolicy` route each vehicle. This
showcases the general-graph capability that the linear-corridor examples do not.

Run: ``python examples/grid_demo.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import ShortestPathPolicy, Vehicle, grid_network  # noqa: E402
from mesoltm.visualizations import plot_network  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/


def main() -> None:
    """Run the grid demo and save a network-state figure."""
    # 4x4 grid minus node (1, 2): a partially connected custom layout.
    net = grid_network(
        4,
        4,
        link_length=200.0,
        spacing=1.0,
        fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15},
        skip_nodes=[(1, 2)],
        all_nodes_od=True,
    )

    # Three OD flows, each from a different corner toward the opposite side, so
    # their shortest paths cross in the middle of the grid.
    flows = {
        (0, 0): (3, 3),
        (3, 0): (0, 3),
        (0, 3): (3, 0),
    }

    # Release 30 vehicles per flow, one every 2 s, giving each a unique id.
    vid = 0
    for origin, dest in flows.items():
        vehicles = []
        for k in range(30):
            vehicles.append(
                Vehicle(
                    vehicle_id=vid, start=float(k * 2), origin=origin, destination=dest
                )
            )
            vid += 1
        net.set_origin(origin, vehicles=vehicles)

    # dynamic=True re-plans on live costs; with no cost override that is just
    # free-flow shortest paths, but it lets congestion influence routing if added.
    sim = net.compile(
        time_step=1.0, total_time=400.0, routing_policy=ShortestPathPolicy(dynamic=True)
    )
    sim.run()

    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
    print(f"Grid demo: {arrived} of {vid} vehicles reached their destination.")

    state = sim.network_state
    assert state is not None  # set by compile()
    matplotlib.use("Agg")
    # Left: the grid's structure (link capacity). Right: which links actually
    # carried traffic over the run (total flow) — the used corridors stand out.
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    plot_network(state, color_by="capacity", ax=axes[0])
    plot_network(state, color_by="flow", ax=axes[1])
    fig.tight_layout()
    print("Figure saved to", savefig(fig, "grid_network_flow", subdir=SUBDIR))


if __name__ == "__main__":
    main()
