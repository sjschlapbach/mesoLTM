# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Demo: a random bottleneck access policy (step + inject + a plugin).

A controller drives the model one tick at a time (``Simulation.start`` / ``step``)
and injects vehicles on demand (``Simulation.inject``). Every vehicle enters at the
origin ``O`` bound for ``G`` and is initially planned along the **fast bottleneck
route** ``O->A->B->G`` (the link ``A->B`` is the bottleneck).

Access to the bottleneck is rationed by a **random access policy**: while a vehicle
is on the approach link ``O->A`` — i.e. *about to enter* the bottleneck — a plugin
tosses a coin once. Heads and the vehicle is admitted (keeps the bottleneck route);
tails and it is denied and rerouted onto a **significantly slower parallel path**
``O->A->S->G``. The coin is tossed **once per bottleneck access**: after a toss the
decision is held and only reset after a cooldown, so the plugin never re-tosses
(and flip-flops) while the vehicle sits on the approach link.

There is no automatic routing here: the simulation uses the default static
route-following policy, and the only route changes are the reroutes the access
policy applies. For four vehicles we plot, side by side, the route **before** the
toss, the route **after** it, and the route actually **driven** — so the rerouting
is visible end to end. The run is also recorded and rendered as a video (and
per-step frames) showing every vehicle first planning the bottleneck and the denied
ones being diverted onto the slow path.

Run: ``python examples/bottleneck_access_policy.py``
"""

from __future__ import annotations

import pathlib
import random
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import OUTPUT_DIR, savefig  # noqa: E402

from mesoltm import Network, ReroutingPlugin, Vehicle  # noqa: E402
from mesoltm.visualizations import (  # noqa: E402
    NetworkLayout,
    save_animation,
)

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

DT = 1.0
TOTAL_TIME = 400.0
N_VEHICLES = 4
RELEASE_TIMES = [5.0, 20.0, 35.0, 50.0]  # when each vehicle is released from O
ACCESS_PROB = 0.5  # a fair coin: P(admitted to the bottleneck)
COOLDOWN = 60  # steps a toss is held before a vehicle could be tossed again
SEED = 1  # fixed so the demo is reproducible (and shows a 2/2 mix of outcomes)

# Node layout: shared approach O->A, then the bottleneck A->B->G and, parallel to
# it, the much slower detour A->S->G. Positions are used only for the plots.
POS = {
    "O": (0.0, 0.0),  # origin (vehicles released here)
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
    net.set_origin("O")  # no static demand; vehicles are injected during the run
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


class RandomBottleneckAccess(ReroutingPlugin):
    """Random admission control: coin-toss each vehicle about to enter the bottleneck.

    While a vehicle is on the approach link, a coin is tossed **once** (subsequent
    steps within ``cooldown`` are ignored, so we never re-toss during the same
    approach). Heads keeps the bottleneck route; tails reroutes the vehicle onto the
    slower parallel path. For every vehicle we record the route just before the toss
    and just after it, so the effect of the reroute can be shown afterwards.
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

        # Per-vehicle bookkeeping, keyed by vehicle id.
        self.decided_at: dict[int, int] = {}  # step of the last toss (for cooldown)
        self.admitted: dict[int, bool] = {}  # coin result of the last toss
        self.route_before: dict[int, list] = {}  # node route just before the toss
        self.route_after: dict[int, list] = {}  # node route just after the toss

    def reroute(self, t, state, vehicles) -> dict:
        """Toss the coin for vehicles newly on the approach link; reroute the denied."""
        updates: dict = {}
        for view in vehicles:
            if view.link_id != self.approach_link:
                continue  # only vehicles *about to enter* the bottleneck are tossed
            vid = view.vehicle.vehicle_id

            # One toss per access: hold the decision until the cooldown elapses, so
            # we neither re-toss every step on the approach nor flip a vehicle's
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
    """Run the random-bottleneck-access demo and save the route figure + video."""
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

    plugin = RandomBottleneckAccess(ids["in"], slow_route, link_nodes, COOLDOWN, SEED)

    def classify(vehicle, state) -> str:  # pylint: disable=unused-argument
        """Colour category per vehicle: undecided until tossed, then the outcome."""
        vid = vehicle.vehicle_id
        if vid not in plugin.decided_at:
            return "undecided"
        return "admitted" if plugin.admitted.get(vid) else "denied"

    # Enable per-step history logging so the run can be animated; persist it to a
    # JSON file too (so the video could also be regenerated from the file later).
    history_path = str(OUTPUT_DIR / SUBDIR / "bottleneck_access_history.json")
    (OUTPUT_DIR / SUBDIR).mkdir(parents=True, exist_ok=True)
    sim = net.compile(
        time_step=DT,
        total_time=TOTAL_TIME,
        plugins=[plugin],
        injection_budget=N_VEHICLES,
        record_history=True,
        history_classify=classify,
        history_path=history_path,
    )
    state = sim.network_state
    assert state is not None  # set by compile()

    vehicles: dict[int, Vehicle] = {}
    released = [False] * N_VEHICLES

    # Control loop: inject each vehicle at its release time, planned via the
    # bottleneck; the access policy then admits or diverts it as it approaches.
    sim.start()
    while sim.current_step < sim.total_steps:
        now = sim.current_step * DT
        for i in range(N_VEHICLES):
            if not released[i] and now >= RELEASE_TIMES[i]:
                vehicle = Vehicle(
                    vehicle_id=i,
                    origin="O",
                    destination="G",
                    route=list(bottleneck_route),
                )
                sim.inject("O", vehicle)
                vehicles[i] = vehicle
                released[i] = True

        sim.step()

    # The route each vehicle actually drove, from its recorded trajectory.
    driven: dict[int, list] = {}
    for i, vehicle in vehicles.items():
        real_links = [
            seg["link_id"] for seg in vehicle.trajectory if not seg["is_connector"]
        ]
        driven[i] = route_to_nodes(real_links, link_nodes)

    print("Random bottleneck access (heads = admitted, tails = diverted to slow path):")
    for i in sorted(vehicles):
        outcome = (
            "admitted -> bottleneck" if plugin.admitted[i] else "denied -> slow path"
        )
        print(f"  vehicle {i}: {outcome};  drove {' -> '.join(driven[i])}")

    matplotlib.use("Agg")
    _plot_routes(plugin, driven, sorted(vehicles))
    _render_animation(sim, ids)


def _render_animation(sim, ids: dict) -> None:
    """Store the per-step frames and a rendered video of the moving vehicles.

    Shows every vehicle first planning the bottleneck (blue, arrow toward ``B``)
    and the denied ones flipping colour and diverting at ``A`` down the slow
    ``A->S->G`` path — the redirection made visible end to end.
    """
    history = sim.history
    assert history is not None  # record_history=True at compile
    sim.save_history()  # write the JSON log (history_path was set at compile)

    # Trim the empty tail (after the last vehicle has arrived) so the clip is tight.
    last = max(
        (i for i, frame in enumerate(history.frames) if frame.agents or frame.waiting),
        default=len(history.frames) - 1,
    )
    frames = history.frames[: last + 8]
    layout = NetworkLayout.from_history(history)
    out_dir = OUTPUT_DIR / SUBDIR

    video = save_animation(
        frames,
        layout,
        str(out_dir / "bottleneck_access.mp4"),
        fps=25,
        subsample=2.0,  # hold each step for 2 frames -> a slower, readable clip
        frames_dir=str(out_dir / "frames"),  # also dump the individual pictures
        palette={
            "undecided": "#4477aa",  # planning the bottleneck
            "admitted": "#228833",  # kept the bottleneck route
            "denied": "#ee7733",  # diverted to the slow parallel path
        },
        highlight_links=[ids["bneck"]],
        title="Random bottleneck access: all plan the bottleneck; some are redirected",
    )
    print("Video saved to", video)
    print("Per-step frames saved under", out_dir / "frames")


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


def _plot_routes(
    plugin: RandomBottleneckAccess, driven: dict, vehicle_ids: list
) -> None:
    """Plot before / after / driven routes (columns) for each vehicle (rows)."""
    col_titles = ["planned (before toss)", "assigned (after toss)", "driven"]
    fig, axes = plt.subplots(
        len(vehicle_ids), 3, figsize=(12, 3.2 * len(vehicle_ids)), squeeze=False
    )
    for row, vid in enumerate(vehicle_ids):
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
        axes[row][0].set_ylabel(f"vehicle {vid}\n({label})", fontsize=9)

    fig.suptitle(
        "Random bottleneck access: each vehicle's route before, after, and driven"
    )
    fig.tight_layout()
    print("\nFigure saved to", savefig(fig, "bottleneck_access_routes", subdir=SUBDIR))


if __name__ == "__main__":
    main()
