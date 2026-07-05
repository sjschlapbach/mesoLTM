# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Demo: animating grids with load-aware dynamic routing.

Two scenarios share the same code:

* a **tiny 2x2 grid** with a handful of vehicles and a short horizon — small enough
  to *manually verify*: the per-step frames and the JSON history log let you check
  each agent's link-by-link path and its logged remaining route by hand;
* a dense **7x7 grid** (with a few holes) carrying many vehicles between random
  origin-destination pairs — the readability stress test.

Routing is dynamic and congestion-aware, but done the **safe, consistent way**: a
:class:`DensityRerouter` plugin re-plans each vehicle's route to its destination on
the live density cost whenever it reaches a new node, and writes the plan back onto
the vehicle (``state.set_route``). Because the plan lives on ``vehicle.route``, the
recorder logs *exactly* the route that ran — the animation never recomputes routes
of its own, so the log can never drift from the simulation (crucial when routing is
an exogenous mid-run intervention like this). Dots are coloured **by the next link
each agent will take**, read straight from that logged route.

Each vehicle also carries free-form ``props`` metadata (here a vehicle class) set
at injection; one still shows colouring driven by a **custom function of that
metadata** instead of the next link, to demonstrate that ``color_by`` is fully
overridable (and that ``props`` travel with the vehicle and round-trip through the
JSON history).

Everything is written to ``examples/output/grid_visualization/``: an MP4 per
scenario, the small scenario's per-step PNGs, three stills for the large one, and
the JSON history **logfile** for each.

Run: ``python examples/grid_visualization.py``
"""

from __future__ import annotations

import pathlib
import random
import sys
from collections.abc import Callable
from typing import Any

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import OUTPUT_DIR, savefig  # noqa: E402

from mesoltm import (  # noqa: E402
    NetworkState,
    ReroutingPlugin,
    ShortestPathPolicy,
    Vehicle,
    grid_network,
)
from mesoltm.visualizations import (  # noqa: E402
    NetworkLayout,
    render_frame,
    save_animation,
)

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

DT = 1.0
DENSITY_PENALTY = 300.0  # seconds of extra routing cost per (veh/m) of density
VEHICLE_CLASSES = ["car", "van", "truck"]  # arbitrary per-vehicle metadata (props)
CLASS_COLORS = {"car": "#0072b2", "van": "#009e73", "truck": "#d55e00"}


def cost(link_id: int, state: NetworkState) -> float:
    """Free-flow time plus a linear penalty in the link's current density."""
    density = state.occupancy(link_id) / state.length(link_id)  # veh/m
    return state.free_flow_time(link_id) + DENSITY_PENALTY * density


class DensityRerouter(ReroutingPlugin):
    """Re-plan each vehicle on the live density cost, at every node it reaches.

    Route-based rerouting (the endorsed exogenous mechanism): whenever a vehicle
    arrives on a new link, the remaining route to its destination is re-planned on
    the current congestion cost and written back via ``state.set_route``. The plan
    therefore always lives on ``vehicle.route``, so the recorder logs precisely the
    route that ran — no route is ever recomputed at recording time.

    Re-planning only on a link change (not every step) keeps it cheap and mirrors a
    node-by-node router: each vehicle commits to its next link and re-evaluates the
    tail one hop later.
    """

    def __init__(self, planner: ShortestPathPolicy) -> None:
        """Store the shortest-path planner and start per-vehicle bookkeeping."""
        super().__init__()
        self.planner = planner
        self._last_link: dict[int, int] = {}

    def reroute(self, t, state, vehicles) -> dict:
        """Return ``{vehicle: new_route}`` for vehicles that reached a new node."""
        # Build the live-cost graph once for the whole step, then reuse it for every
        # vehicle's lookup instead of rebuilding it per call.
        self.planner.refresh(state)
        was_dynamic = self.planner.dynamic
        self.planner.dynamic = False
        try:
            updates: dict = {}
            for view in vehicles:
                vid = view.vehicle.vehicle_id
                if self._last_link.get(vid) == view.link_id:
                    continue  # still on the same link -> keep the committed plan
                self._last_link[vid] = view.link_id
                arriving = state.downstream_node.get(view.link_id)
                tail = self.planner.route(state, arriving, view.vehicle.destination)
                new_route = [view.link_id, *tail]
                if new_route != view.route:
                    updates[view.vehicle] = new_route
            return updates
        finally:
            self.planner.dynamic = was_dynamic


def run_grid(
    rows: int,
    cols: int,
    holes: list,
    n_vehicles: int,
    total_time: float,
    last_release: float,
    seed: int,
    history_path: str,
):
    """Simulate a grid with injected random-OD demand under dynamic rerouting.

    Vehicles are injected over ``[0, last_release]`` at random distinct O/D pairs,
    each seeded with a shortest-path route and then re-planned live by the
    :class:`DensityRerouter`. Returns the populated ``SimulationHistory``.
    """
    net = grid_network(
        rows,
        cols,
        link_length=200.0,
        spacing=1.0,
        fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15},
        skip_nodes=holes,
        all_nodes_od=True,  # any node can be an origin or a destination
    )
    planner = ShortestPathPolicy(cost=cost, dynamic=True)
    pathlib.Path(history_path).parent.mkdir(parents=True, exist_ok=True)
    sim = net.compile(
        time_step=DT,
        total_time=total_time,
        plugins=[DensityRerouter(planner)],
        injection_budget=n_vehicles,
        record_history=True,
        history_path=history_path,
    )
    state = sim.network_state
    assert state is not None  # set by compile()

    present = [(i, j) for i in range(rows) for j in range(cols) if (i, j) not in holes]
    rng = random.Random(seed)
    schedule = []  # (release_time, vehicle_id, origin, destination, vehicle_class)
    for vid in range(n_vehicles):
        origin, dest = rng.sample(present, 2)  # distinct random OD pair
        vclass = rng.choice(VEHICLE_CLASSES)  # arbitrary per-vehicle metadata
        schedule.append((rng.uniform(0.0, last_release), vid, origin, dest, vclass))
    schedule.sort()

    # Control loop: inject each vehicle at its release time with a shortest-path
    # route; the rerouter then adapts it to congestion as the vehicle progresses.
    # Each vehicle carries free-form ``props`` metadata (here a vehicle class) that
    # travels with it and can be used later (e.g. a custom ``color_by``).
    pending = list(schedule)
    sim.start()
    while sim.current_step < sim.total_steps:
        now = sim.current_step * DT
        while pending and pending[0][0] <= now:
            _, vid, origin, dest, vclass = pending.pop(0)
            route = planner.route(state, origin, dest)
            vehicle = Vehicle(
                vid, origin=origin, destination=dest, route=route, props={"cls": vclass}
            )
            sim.inject(origin, vehicle)
        sim.step()

    sim.save_history()  # write the JSON logfile (history_path set at compile)
    arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
    print(f"  {arrived} of {n_vehicles} vehicles arrived; log -> {history_path}")
    assert sim.history is not None
    return sim.history


def _tight_frames(history):
    """Trim the empty tail (after the last vehicle left) so the clip stays tight."""
    last = max(
        (i for i, f in enumerate(history.frames) if f.agents or f.waiting),
        default=len(history.frames) - 1,
    )
    return history.frames[: last + 8]


def _still(
    frame,
    layout,
    name: str,
    title: str,
    color_by: str | Callable[[Any], Any] = "next_link",
    **kw,
) -> None:
    """Render one frame to a PNG under the example's output directory."""
    fig, ax = plt.subplots(figsize=(10, 10))
    render_frame(frame, layout, ax=ax, color_by=color_by, title=title, **kw)
    print("  figure saved to", savefig(fig, name, subdir=SUBDIR))
    plt.close(fig)


def run_small(out_dir: pathlib.Path) -> None:
    """A tiny 2x2 grid for manual verification (frames + log are inspectable)."""
    print("2x2 verification grid:")
    history = run_grid(
        rows=2,
        cols=2,
        holes=[],
        n_vehicles=4,
        total_time=80.0,
        last_release=12.0,
        seed=1,
        history_path=str(out_dir / "grid2x2_history.json"),
    )
    layout = NetworkLayout.from_history(history)
    frames = _tight_frames(history)
    # Slow (subsample=3) and with full per-agent detail + node labels so the small
    # scenario can be checked by eye against the frames and the JSON log.
    video = save_animation(
        frames,
        layout,
        str(out_dir / "grid2x2_movement.mp4"),
        fps=25,
        subsample=3.0,
        frames_dir=str(out_dir / "grid2x2_frames"),  # per-step PNGs to verify by hand
        color_by="next_link",
        detail="full",
        title="2x2 grid — manual verification (coloured by next link)",
    )
    print("  video saved to", video)
    print("  per-step frames saved under", out_dir / "grid2x2_frames")


def run_large(out_dir: pathlib.Path) -> None:
    """A dense 7x7 holed grid — the readability stress test."""
    print("7x7 dense grid:")
    holes = [(1, 1), (1, 4), (3, 3), (4, 1), (5, 5), (2, 5)]  # a few missing nodes
    history = run_grid(
        rows=7,
        cols=7,
        holes=holes,
        n_vehicles=140,
        total_time=300.0,
        last_release=150.0,
        seed=3,
        history_path=str(out_dir / "grid7x7_history.json"),
    )
    layout = NetworkLayout.from_history(history)
    frames = _tight_frames(history)
    video = save_animation(
        frames,
        layout,
        str(out_dir / "grid7x7_movement.mp4"),
        fps=25,
        color_by="next_link",  # colour each dot by the link it will enter next
        title="7x7 grid — agents between random OD pairs (coloured by next link)",
    )
    print("  video saved to", video)

    # A high-quality still at peak load (the readable default detail level) ...
    peak = max(frames, key=lambda f: len(f.agents))
    _still(
        peak, layout, "grid7x7_peak", "7x7 grid at peak load (coloured by next link)"
    )
    # ... and a lighter moment with full per-agent detail on select (ids +
    # next-link arrows), which stays legible when the network is not packed.
    moderate = min(frames, key=lambda f: abs(len(f.agents) - 12))
    _still(
        moderate,
        layout,
        "grid7x7_detailed",
        "Full detail on select: per-agent ids + next-link arrows",
        detail="full",
        show_node_labels=False,
    )
    # ... and the same peak moment coloured by a *custom* function of each
    # vehicle's own metadata (its ``props["cls"]``), with a fixed palette — showing
    # colouring can be driven by arbitrary per-vehicle information, not just the
    # next link. The class was set on each vehicle at injection and travels with it
    # (it even round-trips through the JSON history).
    _still(
        peak,
        layout,
        "grid7x7_by_class",
        "Custom colouring by vehicle class (from vehicle props)",
        color_by=lambda item: item.props.get("cls", "car"),
        palette=CLASS_COLORS,
    )


def main() -> None:
    """Run the 2x2 verification grid and the dense 7x7 grid; render both."""
    matplotlib.use("Agg")
    out_dir = OUTPUT_DIR / SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    run_small(out_dir)
    run_large(out_dir)


if __name__ == "__main__":
    main()
