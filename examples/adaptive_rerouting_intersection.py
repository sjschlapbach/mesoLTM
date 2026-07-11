"""Demo: per-step adaptive rerouting through one uncontrolled intersection.

The network is the most basic multi-incoming / multi-outgoing setup: a single
central junction ``X`` with two incoming approaches (from origins ``O1`` and
``O2``) and two outgoing links (toward ``P`` and ``Q``, which each lead on to the
destination ``D``). ``X`` is therefore modelled by the general node model, which
resolves the two approaches by priority with no signal — an uncontrolled
("no-way-stop") intersection. The two outgoing links give every agent a genuine
route choice: ``X -> P -> D`` or ``X -> Q -> D``.

Each agent carries an explicit planned route. Every time step a plugin re-checks,
for each agent on a link, whether that plan is still the shortest route to ``D``
from the downstream end of its current link under live (congestion-dependent)
costs. Agents never turn around on a link, so only the tail from the current
link's downstream node is rewritten. Plan changes are versioned per agent so we
can show, afterwards, how a rerouted agent's plan evolved.

The cost model, plugin and plotting all live in this script (specific demo).

Run: ``python examples/adaptive_rerouting_intersection.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import Network, Plugin, Vehicle  # noqa: E402

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

FD = {"v_f": 15.0, "w": 5.0, "rho_jam": 0.15}
LINK_LEN = 200.0
DT, TOTAL_TIME = 1.0, 300.0
N_PER_ORIGIN, HEADWAY = 18, 1.5  # two approaches => ~1.3 veh/s onto a ~0.56 corridor
ORIGINS = [(0, 1), (0, -1)]
DESTINATION = (3, 0)
# BPR-style congestion cost: travel time grows with how full a link is.
BPR_ALPHA, BPR_BETA = 4.0, 2.0

# Node layout: two origins -> central intersection X -> two branches -> destination.
POS = {
    (0, 1): (0.0, 1.0),  # O1
    (0, -1): (0.0, -1.0),  # O2
    (1, 0): (1.0, 0.0),  # X  (uncontrolled 2-in / 2-out intersection)
    (2, 1): (2.0, 1.0),  # P
    (2, -1): (2.0, -1.0),  # Q
    (3, 0): (3.0, 0.0),  # D
}
EDGES = [
    ((0, 1), (1, 0)),  # O1 -> X
    ((0, -1), (1, 0)),  # O2 -> X
    ((1, 0), (2, 1)),  # X  -> P
    ((1, 0), (2, -1)),  # X  -> Q
    ((2, 1), (3, 0)),  # P  -> D
    ((2, -1), (3, 0)),  # Q  -> D
]


def link_cost(state, link_id: int) -> float:
    """Live routing cost of a link: free-flow time inflated by its occupancy."""
    link = state.links_by_id[link_id]
    jam_storage = link.rho_jam * link.length
    saturation = state.occupancy(link_id) / jam_storage if jam_storage else 0.0
    return state.continuous_free_flow_time(link_id) * (
        1.0 + BPR_ALPHA * saturation**BPR_BETA
    )


def cost_graph(state) -> nx.DiGraph:
    """Build a directed graph of real links weighted by current cost (cheapest edge)."""
    g = nx.DiGraph()
    for lid in state.link_ids():
        ep = state.endpoints(lid)
        if ep is None:  # skip auto-inserted O/D connectors
            continue
        u, v = ep
        c = link_cost(state, lid)
        if not g.has_edge(u, v) or c < g[u][v]["cost"]:
            g.add_edge(u, v, cost=c, link_id=lid)
    return g


def route_to_nodes(route: list[int], state) -> tuple:
    """Convert a link-id route to the node sequence it visits (connectors dropped)."""
    nodes: list = []
    for lid in route:
        ep = state.endpoints(lid)
        if ep is None:
            continue
        u, v = ep
        if not nodes:
            nodes.append(u)
        nodes.append(v)
    return tuple(nodes)


class AdaptiveRerouter(Plugin):
    """Rewrites each on-link agent's remaining route to the live shortest path.

    The already-travelled prefix (up to and including the current link) is kept, so
    an agent never reverses; only the tail from the current link's downstream node
    onward is recomputed. Every change is appended to ``versions[vehicle_id]``.
    """

    def __init__(self, versions: dict) -> None:
        super().__init__()
        self.versions = versions
        self.reroute_count = 0

    def run_step(self, t: int) -> None:
        state = self.state
        assert state is not None
        graph = cost_graph(state)

        for lid in state.link_ids():
            ep = state.endpoints(lid)
            if ep is None:
                continue
            u, v = ep
            for vehicle in list(state.links_by_id[lid].vehicles):
                if v == vehicle.destination:
                    continue  # on the final link; nothing left to reroute
                self._maybe_reroute(t, vehicle, lid, u, v, graph, state)

    def _maybe_reroute(self, t, vehicle, lid, u, v, graph, state) -> None:
        """Recompute the tail route from node ``v`` and apply it if it changed."""
        # "No turning around": forbid the immediate reverse edge v -> u.
        reverse = graph[v].get(u) if graph.has_node(v) else None
        if reverse is not None:
            graph.remove_edge(v, u)
        try:
            node_path = nx.shortest_path(graph, v, vehicle.destination, weight="cost")
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            node_path = None
        if reverse is not None:
            graph.add_edge(v, u, **reverse)
        if not node_path:
            return

        suffix = [
            graph[a][b]["link_id"]
            for a, b in zip(node_path[:-1], node_path[1:], strict=True)
        ]
        sink = state.sink_connectors.get(vehicle.destination)
        new_tail = [lid] + suffix + ([sink] if sink is not None else [])

        idx = vehicle.position
        if not (0 <= idx < len(vehicle.route) and vehicle.route[idx] == lid):
            idx = vehicle.route.index(lid)
        if new_tail == vehicle.route[idx:]:
            return  # plan unchanged

        vehicle.route = vehicle.route[:idx] + new_tail
        vehicle.position = idx
        self.reroute_count += 1
        self.versions[vehicle.vehicle_id].append(
            (t, route_to_nodes(vehicle.route, state))
        )


def build_network() -> tuple[Network, dict]:
    """Assemble the network; return it with its ``(u, v) -> link_id`` map."""
    net = Network(default_fd=FD)
    for node, pos in POS.items():
        net.add_node(node, pos=pos)
    link_of = {(u, v): net.add_link(u, v, length=LINK_LEN) for u, v in EDGES}
    return net, link_of


def main() -> None:
    """Run the scenario, report reroutes, and plot sampled agents' plans."""
    net, link_of = build_network()

    # Every agent starts with the free-flow shortest plan from its origin.
    hop_graph = nx.DiGraph(list(link_of))
    initial_nodes = {
        origin: nx.shortest_path(hop_graph, origin, DESTINATION) for origin in ORIGINS
    }

    agents, versions = [], {}
    for origin in ORIGINS:
        route = [
            link_of[(a, b)]
            for a, b in zip(
                initial_nodes[origin][:-1], initial_nodes[origin][1:], strict=True
            )
        ]
        origin_agents = [
            Vehicle(
                vehicle_id=len(agents) + k,
                start=k * HEADWAY,
                origin=origin,
                destination=DESTINATION,
                route=list(route),
            )
            for k in range(N_PER_ORIGIN)
        ]
        for agent in origin_agents:
            versions[agent.vehicle_id] = [(0, tuple(initial_nodes[origin]))]
        net.set_origin(origin, vehicles=origin_agents)
        agents.extend(origin_agents)
    net.set_destination(DESTINATION)

    rerouter = AdaptiveRerouter(versions)
    sim = net.compile(time_step=DT, total_time=TOTAL_TIME, plugins=[rerouter])
    sim.run()

    rerouted = [k for k, v in versions.items() if len(v) > 1]
    print(f"Agents: {len(agents)}   route changes applied: {rerouter.reroute_count}")
    print(f"Agents that were rerouted at least once: {len(rerouted)}")

    sample = rerouted[:: max(1, len(rerouted) // 3)][:3]
    for vid in sample:
        print(f"\nAgent {vid} — {len(versions[vid])} route versions:")
        for t, node_seq in (versions[vid][0], versions[vid][-1]):
            arrows = " -> ".join(str(n) for n in node_seq)
            tag = "initial" if t == 0 else f"t={t:>3}"
            print(f"  [{tag}] {arrows}")

    if not sample:
        print("\nNo agent was rerouted (try more agents or a lower HEADWAY).")
        return

    matplotlib.use("Agg")
    fig, axes = plt.subplots(
        1, len(sample), figsize=(4.5 * len(sample), 4.5), squeeze=False
    )
    for ax, vid in zip(axes[0], sample, strict=True):
        for a, b in EDGES:  # faint network backdrop
            ax.plot(
                [POS[a][0], POS[b][0]],
                [POS[a][1], POS[b][1]],
                color="0.85",
                lw=1.0,
                zorder=1,
            )
        _draw_route(ax, versions[vid][0][1], "#4477aa", "--", "initial plan", 0.0)
        _draw_route(ax, versions[vid][-1][1], "#cc3311", "-", "final plan", 0.05)
        for node, label, color in _od_markers():
            ax.scatter(*POS[node], s=140, c=color, zorder=4)
            ax.annotate(label, POS[node], textcoords="offset points", xytext=(6, 6))
        ax.set_title(f"agent {vid}: {len(versions[vid])} versions")
        ax.legend(loc="lower right", fontsize=8)
        ax.set_aspect("equal")
        ax.axis("off")
    fig.tight_layout()
    print("\nFigure saved to", savefig(fig, "agent_reroute_plans", subdir=SUBDIR))


def _od_markers() -> list:
    """Return (node, label, colour) markers for the origins and destination."""
    markers = [(origin, f"O{i + 1}", "green") for i, origin in enumerate(ORIGINS)]
    markers.append((DESTINATION, "D", "black"))
    return markers


def _draw_route(ax, node_seq, color, style, label, offset) -> None:
    """Draw a route as a polyline through node positions (small offset for overlap)."""
    xs = [POS[n][0] + offset for n in node_seq]
    ys = [POS[n][1] + offset for n in node_seq]
    ax.plot(xs, ys, color=color, linestyle=style, lw=2.5, label=label, zorder=3)


if __name__ == "__main__":
    main()
