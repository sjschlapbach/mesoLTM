# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Demo: ride-hail drivers and a coin-tossed bottleneck (step + inject + a plugin).

An external dispatcher drives the model one tick at a time (``Simulation.start`` /
``step``) and injects drivers on demand (``Simulation.inject``). Every driver is
dispatched from the origin ``O`` to the goal ``G`` and initially planned along the
**fast bottleneck route** ``O->A->B->G`` (the link ``A->B`` is the bottleneck).

Access to the bottleneck is rationed by a **coin toss**: while a driver is on the
approach link ``O->A`` — i.e. *about to enter* the bottleneck — a plugin tosses a
coin once. Heads and the driver is admitted (keeps the bottleneck route); tails and
it is denied and manually rerouted onto a **significantly slower parallel path**
``O->A->S->G``. The coin is tossed **once per bottleneck access**: after a toss the
driver's decision is held and only reset after a cooldown, so the plugin never
re-tosses (and flip-flops) while the driver sits on the approach link.

There is no automatic routing here: the simulation uses the default static
route-following policy, and the only route changes are the manual reroutes the
coin-toss plugin applies. For four drivers we plot, side by side, the route
**before** the coin toss, the route **after** it, and the route actually **driven**
— so the manual rerouting is visible end to end.

Run: ``python examples/ride_hail_dispatch.py``
"""

from __future__ import annotations

import pathlib
import random
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import Network, ReroutingPlugin, Vehicle  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

DT = 1.0
TOTAL_TIME = 400.0
N_DRIVERS = 4
DISPATCH_TIMES = [5.0, 20.0, 35.0, 50.0]  # when each driver is dispatched from O
ACCESS_PROB = 0.5  # a fair coin: P(admitted to the bottleneck)
COOLDOWN = 60  # steps a toss is held before the driver could be tossed again
SEED = 1  # fixed so the demo is reproducible (and shows a 2/2 mix of outcomes)

# Node layout: shared approach O->A, then the bottleneck A->B->G and, parallel to
# it, the much slower detour A->S->G. Positions are used only for the plots.
POS = {
    "O": (0.0, 0.0),  # origin (drivers dispatched here)
    "A": (1.0, 0.0),  # decision point, just before the bottleneck
    "B": (2.0, 0.0),  # just past the bottleneck
    "G": (3.0, 0.0),  # goal
    "S": (1.5, -1.2),  # waypoint on the slow parallel path
}
EDGES = [("O", "A"), ("A", "B"), ("B", "G"), ("A", "S"), ("S", "G")]
BOTTLENECK_EDGE = ("A", "B")


def build_network() -> tuple[Network, dict]:
    """Build the approach + bottleneck + slow-parallel network; return link ids."""
    net = Network(default_fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15})
    for node, pos in POS.items():
        net.add_node(node, pos=pos)

    ids = {
        "in": net.add_link("O", "A", length=200.0),  # approach to the bottleneck
        "bneck": net.add_link("A", "B", length=200.0, rho_jam=0.06),  # the bottleneck
        "b_g": net.add_link("B", "G", length=200.0),  # bottleneck -> goal
        # Parallel path: longer *and* slower (lower free-flow speed) => much slower.
        "slow1": net.add_link("A", "S", length=600.0, v_f=8.0),
        "slow2": net.add_link("S", "G", length=600.0, v_f=8.0),
    }
    net.set_origin("O")  # no static demand; drivers are injected during the run
    net.set_destination("G")
    return net, ids


def route_to_nodes(link_route: list[int], link_nodes: dict) -> list:
    """Convert a real-link route to the sequence of nodes it visits."""
    nodes: list = []
    for lid in link_route:
        u, v = link_nodes[lid]
        if not nodes:
            nodes.append(u)
        nodes.append(v)
    return nodes


class BottleneckCoinToss(ReroutingPlugin):
    """Admission control: coin-toss each driver about to enter the bottleneck.

    While a driver is on the approach link, a coin is tossed **once** (subsequent
    steps within ``cooldown`` are ignored, so we never re-toss during the same
    approach). Heads keeps the bottleneck route; tails reroutes the driver onto the
    slower parallel path. For every driver we record the route just before the toss
    and just after it, so the effect of the manual reroute can be shown afterwards.
    """

    def __init__(
        self,
        approach_link: int,
        slow_route: list[int],
        link_nodes: dict,
        cooldown: int,
        seed: int,
    ) -> None:
        super().__init__()
        self.approach_link = approach_link
        self.slow_route = list(slow_route)
        self.link_nodes = link_nodes
        self.cooldown = cooldown
        self.rng = random.Random(seed)

        # Per-driver bookkeeping, keyed by vehicle id.
        self.decided_at: dict[int, int] = {}  # step of the last toss (for cooldown)
        self.admitted: dict[int, bool] = {}  # coin result of the last toss
        self.route_before: dict[int, list] = {}  # node route just before the toss
        self.route_after: dict[int, list] = {}  # node route just after the toss

    def reroute(self, t, state, vehicles) -> dict:
        """Toss the coin for drivers newly on the approach link; reroute the denied."""
        updates: dict = {}
        for view in vehicles:
            if view.link_id != self.approach_link:
                continue  # only drivers *about to enter* the bottleneck are tossed
            vid = view.vehicle.vehicle_id

            # One toss per access: hold the decision until the cooldown elapses, so
            # we neither re-toss every step on the approach nor flip a driver's
            # choice mid-approach. After the cooldown a fresh access could re-toss.
            if vid in self.decided_at and t - self.decided_at[vid] < self.cooldown:
                continue

            self.decided_at[vid] = t
            self.route_before[vid] = route_to_nodes(view.route, self.link_nodes)
            admitted = self.rng.random() < ACCESS_PROB
            self.admitted[vid] = admitted
            if admitted:
                self.route_after[vid] = list(self.route_before[vid])  # unchanged
            else:
                updates[view.vehicle] = list(self.slow_route)  # divert to slow path
                self.route_after[vid] = route_to_nodes(self.slow_route, self.link_nodes)
        return updates


def main() -> None:
    """Run the coin-tossed-bottleneck ride-hail demo and save the route figure."""
    net, ids = build_network()
    link_nodes = {
        ids["in"]: ("O", "A"),
        ids["bneck"]: ("A", "B"),
        ids["b_g"]: ("B", "G"),
        ids["slow1"]: ("A", "S"),
        ids["slow2"]: ("S", "G"),
    }
    bottleneck_route = [ids["in"], ids["bneck"], ids["b_g"]]
    slow_route = [ids["in"], ids["slow1"], ids["slow2"]]

    plugin = BottleneckCoinToss(ids["in"], slow_route, link_nodes, COOLDOWN, SEED)
    sim = net.compile(
        time_step=DT,
        total_time=TOTAL_TIME,
        plugins=[plugin],
        injection_budget=N_DRIVERS,
    )
    state = sim.network_state
    assert state is not None  # set by compile()

    drivers: dict[int, Vehicle] = {}
    dispatched = [False] * N_DRIVERS

    # Dispatcher loop: inject each driver at its dispatch time, planned via the
    # bottleneck; the coin-toss plugin then admits or diverts it as it approaches.
    sim.start()
    while sim.current_step < sim.total_steps:
        now = sim.current_step * DT
        for i in range(N_DRIVERS):
            if not dispatched[i] and now >= DISPATCH_TIMES[i]:
                vehicle = Vehicle(
                    vehicle_id=i,
                    origin="O",
                    destination="G",
                    route=list(bottleneck_route),
                )
                sim.inject("O", vehicle)
                drivers[i] = vehicle
                dispatched[i] = True

        sim.step()

    # The route each driver actually drove, from its recorded trajectory.
    driven: dict[int, list] = {}
    for i, vehicle in drivers.items():
        real_links = [
            seg["link_id"] for seg in vehicle.trajectory if not seg["is_connector"]
        ]
        driven[i] = route_to_nodes(real_links, link_nodes)

    print("Coin-tossed bottleneck (heads = admitted, tails = diverted to slow path):")
    for i in sorted(drivers):
        outcome = (
            "admitted -> bottleneck" if plugin.admitted[i] else "denied -> slow path"
        )
        print(f"  driver {i}: {outcome};  drove {' -> '.join(driven[i])}")

    matplotlib.use("Agg")
    _plot_routes(plugin, driven, sorted(drivers))


def _decision_color(admitted: bool) -> str:
    """Green when admitted to the bottleneck, orange when diverted to the slow path."""
    return "#228833" if admitted else "#ee7733"


def _draw_network(ax) -> None:
    """Draw the network backdrop with the bottleneck link highlighted."""
    for a, b in EDGES:
        if (a, b) == BOTTLENECK_EDGE:
            ax.plot(  # the bottleneck, dashed red
                [POS[a][0], POS[b][0]],
                [POS[a][1], POS[b][1]],
                color="#cc3311",
                lw=2.0,
                linestyle="--",
                zorder=1,
            )
        else:
            ax.plot(
                [POS[a][0], POS[b][0]],
                [POS[a][1], POS[b][1]],
                color="0.8",
                lw=1.5,
                zorder=1,
            )
    for node, (x, y) in POS.items():
        ax.scatter(x, y, s=150, color="white", edgecolors="black", zorder=3)
        ax.annotate(node, (x, y), ha="center", va="center", fontsize=7, zorder=4)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.margins(0.15)


def _draw_route(ax, node_seq: list, color: str) -> None:
    """Draw a route as a thick polyline through the node positions."""
    if not node_seq:
        return
    xs = [POS[n][0] for n in node_seq]
    ys = [POS[n][1] for n in node_seq]
    ax.plot(xs, ys, color=color, lw=3.0, zorder=2, solid_capstyle="round")


def _plot_routes(plugin: BottleneckCoinToss, driven: dict, driver_ids: list) -> None:
    """Plot before / after / driven routes (columns) for each driver (rows)."""
    col_titles = ["planned (before toss)", "assigned (after toss)", "driven"]
    fig, axes = plt.subplots(
        len(driver_ids), 3, figsize=(12, 3.2 * len(driver_ids)), squeeze=False
    )
    for row, vid in enumerate(driver_ids):
        admitted = plugin.admitted[vid]
        # Before = the planned bottleneck route (blue); after and driven take the
        # decision colour (green if admitted, orange if diverted to the slow path).
        panels = [
            (plugin.route_before.get(vid), "#4477aa"),
            (plugin.route_after.get(vid), _decision_color(admitted)),
            (driven.get(vid), _decision_color(admitted)),
        ]
        for col, (route, color) in enumerate(panels):
            ax = axes[row][col]
            _draw_network(ax)
            _draw_route(ax, route, color)
            if row == 0:
                ax.set_title(col_titles[col])
        label = "admitted" if admitted else "denied"
        axes[row][0].set_ylabel(f"driver {vid}\n({label})", fontsize=9)

    fig.suptitle(
        "Coin-tossed bottleneck: each driver's route before, after, and driven"
    )
    fig.tight_layout()
    print("\nFigure saved to", savefig(fig, "ride_hail_coin_toss", subdir=SUBDIR))


if __name__ == "__main__":
    main()
