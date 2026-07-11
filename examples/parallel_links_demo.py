"""Demo: parallel links between two nodes -- fast lane, slow lane and a detour.

Between a single pair of nodes we add three parallel links: a fast lane, a slow
lane (lower free-flow speed), and a detour (a much longer link, modelling a
roundabout route without adding intermediate nodes). Shortest-path routing sends
each vehicle down whichever link is cheapest right now.

Two cases are run on the *same* network:

* **Case 1 -- free-flow routing.** Cost is just each link's free-flow travel time,
  so everyone takes the fast lane until a plugin closes it mid-run; the remaining
  traffic then falls back to the next-cheapest link (the slow lane). The detour is
  never worth taking. This is the original scenario, unchanged.
* **Case 2 -- congestion-aware routing.** The anticipated cost of a link grows with
  how many vehicles are already on it (``cost = free-flow time + LOAD_WEIGHT *
  occupancy``), the fast lane closes later, and vehicles are fed in over a longer
  window. Now, even *before* the closure, the filling fast lane makes the slow lane
  and eventually the detour look cheaper, so some traffic spills onto them -- a
  slight but visible shift towards the detour that free-flow routing never produces.

Run: ``python examples/parallel_links_demo.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import (  # noqa: E402
    FunctionPlugin,
    Network,
    ShortestPathPolicy,
    Vehicle,
)
from mesoltm.visualizations import plot_link_flows, plot_network  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

# A small time step keeps the routing decisions and flow curves smooth; the two
# cases share it so their results are directly comparable.
DT = 0.5
TOTAL_TIME = 320.0
LANE_NAMES = ["fast", "slow", "detour"]
# Interval (seconds) over which the per-lane flow curves are averaged/sampled.
# Set in real time so it stays readable independently of the small DT above.
FLOW_WINDOW_S = 5.0

# Case 1: free-flow routing (LOAD_WEIGHT = 0), fast lane closed early, a short
# demand pulse -- the original scenario, expressed in seconds so it is unchanged.
BASELINE = {
    "load_weight": 0.0,
    "close_time": 20.0,
    "n_vehicles": 60,
    "insert_span": 60.0,
}

# Case 2: congestion-aware routing. Each vehicle already on a link adds
# LOAD_WEIGHT seconds to that link's anticipated cost, the fast lane closes much
# later, and 150 vehicles are fed in over a longer window (~150 steps at DT), so
# the fast lane congests enough to push some traffic onto the slow lane and detour.
CONGESTION = {
    "load_weight": 2.0,
    "close_time": 90.0,
    "n_vehicles": 150,
    "insert_span": 75.0,
}


def build_network():
    """Build A->B with three parallel links and B->C to a destination."""
    net = Network()
    net.add_node("A", pos=(0.0, 0.0))
    net.add_node("B", pos=(1.0, 0.0))
    net.add_node("C", pos=(2.0, 0.0))

    # Three parallel A->B links: a fast lane, a slower lane, and a long detour
    # (same speed as the fast lane but 4x the length, so far cheaper to skip).
    fast = net.add_link("A", "B", length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)
    slow = net.add_link("A", "B", length=300.0, v_f=12.0, w=6.0, rho_jam=0.2)
    detour = net.add_link("A", "B", length=1200.0, v_f=30.0, w=6.0, rho_jam=0.2)
    net.add_link("B", "C", length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)

    net.set_origin("A")
    net.set_destination("C")
    return net, fast, slow, detour


def run_case(load_weight, close_time, n_vehicles, insert_span):
    """Run one parallel-links scenario and return ``(sim, state, lane_ids)``.

    The routing cost is ``free-flow time + load_weight * (vehicles on the link)``,
    plus a prohibitive penalty on the fast lane once it is closed. ``load_weight=0``
    recovers pure free-flow routing (Case 1); a positive weight makes routing
    congestion-aware (Case 2). Vehicles are released evenly over the first
    ``insert_span`` seconds, and the fast lane is closed once at ``close_time``.
    """
    net, fast, slow, detour = build_network()

    # Feed the demand in evenly over the first `insert_span` seconds.
    headway = insert_span / n_vehicles
    vehicles = [
        Vehicle(vehicle_id=k, start=k * headway, origin="A", destination="C")
        for k in range(n_vehicles)
    ]
    net.set_origin("A", vehicles=vehicles)

    # A mutable set of closed link ids that the routing cost reads and the plugin
    # fills; closing a link just means giving it a prohibitive anticipated cost.
    closed: set = set()
    close_step = round(close_time / DT)

    def cost(link_id, state):
        congestion = load_weight * state.occupancy(link_id)
        blocked = 1e6 if link_id in closed else 0.0
        return state.continuous_free_flow_time(link_id) + congestion + blocked

    def close_fast_lane(t, state):
        if t == close_step:
            closed.add(fast)  # close the fast lane once, at close_time

    # dynamic=True rebuilds the cost graph every decision, so the live occupancy
    # term (and the closure) take effect immediately as the network fills.
    policy = ShortestPathPolicy(cost=cost, dynamic=True)
    sim = net.compile(
        time_step=DT,
        total_time=TOTAL_TIME,
        routing_policy=policy,
        plugins=[FunctionPlugin(close_fast_lane)],
    )
    sim.run()

    state = sim.network_state
    assert state is not None  # set by compile()
    return sim, state, (fast, slow, detour)


def lane_split(state, lane_ids) -> dict:
    """Return ``{lane_name: vehicles that used it}`` from the cumulative outflows."""
    total_steps = int(TOTAL_TIME / DT)
    return {
        name: state.cumulative_outflow(lid, total_steps)
        for name, lid in zip(LANE_NAMES, lane_ids)
    }


def _print_split(title: str, split: dict) -> None:
    """Print one case's per-lane vehicle counts on a single line."""
    counts = "   ".join(f"{name}: {split[name]:.0f}" for name in LANE_NAMES)
    print(f"{title:<28s} {counts}")


def main() -> None:
    """Run both cases, report the lane split, and save a comparison figure."""
    base_sim, base_state, base_ids = run_case(**BASELINE)
    cong_sim, cong_state, cong_ids = run_case(**CONGESTION)

    print("Vehicles taking each A->B lane:")
    _print_split("Case 1 (free-flow)", lane_split(base_state, base_ids))
    _print_split("Case 2 (congestion-aware)", lane_split(cong_state, cong_ids))
    print(
        "Congestion-aware routing spreads traffic onto the slow lane and detour "
        "instead of piling it all on the fast lane."
    )

    matplotlib.use("Agg")
    # One row per case: left, the fanned parallel links coloured by total flow;
    # right, per-lane flow over time. Case 2's rows show flow on the slow lane and
    # detour building up while the fast lane is still open.
    cases = [
        (base_sim, base_state, base_ids, "Case 1 - free-flow (fast lane closes 20 s)"),
        (
            cong_sim,
            cong_state,
            cong_ids,
            "Case 2 - congestion-aware (fast lane closes 90 s)",
        ),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for row, (sim, state, lane_ids, title) in enumerate(cases):
        plot_network(state, color_by="flow", ax=axes[row, 0])
        axes[row, 0].set_title(title)  # A->B links fanned apart, coloured by flow
        plot_link_flows(
            sim,
            list(lane_ids),
            labels=LANE_NAMES,
            window_seconds=FLOW_WINDOW_S,
            ax=axes[row, 1],
        )
        axes[row, 1].set_title(f"{title}\n(per-lane flow over time)")
    fig.tight_layout()
    print("\nFigure saved to", savefig(fig, "parallel_links_flow", subdir=SUBDIR))


if __name__ == "__main__":
    main()
