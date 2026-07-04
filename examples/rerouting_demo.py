"""Demo: manually reassigning individual vehicles' routes mid-simulation.

Dynamic (automatic) re-routing is intentionally **switched off** here: the
simulation uses the default static route-following policy, so every vehicle simply
drives the route stored on it and the node models never search for a shortest path.
All route changes come solely from a :class:`ReroutingPlugin` that **hand-picks
specific vehicles and rewrites their routes** — no closed links, no cost model, no
shortest-path search.

The network is a small diamond: a shared entry link ``O->A``, then two ways to the
destination ``D`` -- a direct link ``A->D`` and a longer detour ``A->B->D``. Every
vehicle starts assigned the direct route. While a chosen subset (here, the
odd-numbered vehicles) is still on the entry link, the plugin swaps their route to
the detour -- a purely manual, per-vehicle decision. The result is a deliberate
split of the traffic across the two routes.

Because routes live on the :class:`~mesoltm.Vehicle` objects and the network only
propagates vehicles along whatever route they hold, rewriting ``vehicle.route`` is
all it takes to reroute one vehicle; the others are untouched.

Run: ``python examples/rerouting_demo.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import Network, ReroutingPlugin, Vehicle  # noqa: E402
from mesoltm.visualizations import plot_link_flows, plot_network  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

DT = 1.0
TOTAL_TIME = 400.0
N_VEHICLES = 40
FD = {"v_f": 15.0, "w": 5.0, "rho_jam": 0.15}


def is_rerouted(vehicle_id: int) -> bool:
    """The manually chosen subset to divert onto the detour (odd-numbered here)."""
    return vehicle_id % 2 == 1


def build_network() -> tuple[Network, dict]:
    """Build O->A, then a direct A->D and a longer A->B->D detour; return link ids.

    We build the network explicitly (rather than via ``grid_network``) so we can
    hold the individual link ids and assign each vehicle a concrete static route.
    """
    net = Network(default_fd=FD)
    for node, pos in {
        "O": (0.0, 0.0),  # origin
        "A": (1.0, 0.0),  # split point (after the shared entry link)
        "B": (2.0, 1.0),  # detour waypoint, up and over
        "D": (3.0, 0.0),  # destination
    }.items():
        net.add_node(node, pos=pos)

    ids = {
        "in": net.add_link("O", "A", length=200.0),  # shared entry link
        "direct": net.add_link("A", "D", length=400.0),  # direct route
        "det1": net.add_link("A", "B", length=250.0),  # detour, first leg
        "det2": net.add_link("B", "D", length=250.0),  # detour, second leg
    }
    net.set_destination("D")
    return net, ids


def main() -> None:
    """Run the manual-rerouting demo and save the flow figure."""
    net, ids = build_network()

    # Every vehicle starts assigned the *direct* route O->A->D.
    direct_route = [ids["in"], ids["direct"]]
    detour_route = [ids["in"], ids["det1"], ids["det2"]]
    vehicles = [
        Vehicle(
            vehicle_id=k,
            start=float(k),
            origin="O",
            destination="D",
            route=list(direct_route),
        )
        for k in range(N_VEHICLES)
    ]
    net.set_origin("O", vehicles=vehicles)

    def reroute(_t, _state, in_network):
        """Hand the chosen vehicles the detour route; leave everyone else alone.

        We act only while a target vehicle is still on the shared entry link
        ``in``, so the replacement route starts at its current link (as
        ``set_route`` requires) and only the tail after ``in`` changes. The choice
        of which vehicles to divert is entirely ours -- no cost or path search.
        """
        updates = {}
        for view in in_network:
            if (
                is_rerouted(view.vehicle.vehicle_id)
                and view.link_id == ids["in"]
                and view.route != detour_route
            ):
                updates[view.vehicle] = list(detour_route)

        return updates

    # routing_policy is left as the default (static route-following), so dynamic
    # shortest-path re-routing is OFF: vehicles execute exactly the routes they
    # hold, and the only route changes are the manual ones made by the plugin.
    sim = net.compile(
        time_step=DT, total_time=TOTAL_TIME, plugins=[ReroutingPlugin(reroute)]
    )
    sim.run()

    state = sim.network_state
    assert state is not None  # set by compile()

    via_direct = state.cumulative_outflow(ids["direct"], sim.total_steps)
    via_detour = state.cumulative_outflow(ids["det2"], sim.total_steps)
    n_targeted = sum(1 for v in vehicles if is_rerouted(v.vehicle_id))
    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)

    print(f"Manual rerouting demo: {arrived} of {len(vehicles)} vehicles arrived.")
    print(f"  manually reassigned to the detour: {n_targeted} vehicles")
    print(f"  took the direct route (A->D):      {via_direct:.0f} vehicles")
    print(f"  took the detour (A->B->D):         {via_detour:.0f} vehicles")

    matplotlib.use("Agg")
    # Left: the diamond coloured by total flow -- both the direct link and the
    # detour legs carry traffic, showing the manual split. Right: flow over time on
    # the direct route vs the manually-assigned detour.
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    plot_network(state, color_by="flow", annotate_links=True, ax=axes[0])
    plot_link_flows(
        sim,
        [ids["direct"], ids["det1"]],
        labels=["direct route", "manual detour"],
        window=20,
        ax=axes[1],
    )
    axes[1].set_title("Direct route vs manually-assigned detour")
    fig.tight_layout()
    print("\nFigure saved to", savefig(fig, "rerouting_network_flow", subdir=SUBDIR))


if __name__ == "__main__":
    main()
