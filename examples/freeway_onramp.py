"""Freeway on-ramp merge on a calibrated topology (synthetic demand).

Builds an upstream mainline, a short transition section, a one-lane on-ramp
merging in, and a downstream section, using the calibrated fundamental diagram of
the real-world US-101 freeway merge from de Souza et al. (SIMPAT 140 (2025)
103088, Section 4.5). The original study used proprietary PeMS loop-detector data
that is not distributed with the model, so this script drives the same network
with a **synthetic** demand profile (a mainline peak plus a steady ramp) to
demonstrate the discrete LTM's merge dynamics on the calibrated topology.

Run: ``python examples/freeway_onramp.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import (  # noqa: E402
    DestinationNode,
    Link,
    MergeNode,
    OneToOneNode,
    OriginNode,
    Simulation,
    vehicles_from_demand_profile,
)
from mesoltm.visualizations import (  # noqa: E402
    plot_cumulative_curves,
    plot_link_flows,
)

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

# Calibrated per-lane fundamental diagram from Table 1 of the paper.
V_F, W, RHO_JAM = 29.58, 5.532, 0.1059
DT = 1.0
TOTAL_TIME = 3600.0

# Synthetic demand (veh/s): mainline peaks above capacity mid-horizon; steady ramp.
MAINLINE = [0.9, 1.1, 1.4, 1.4, 1.1, 0.8]  # 3-lane mainline (per 600 s)
RAMP = [0.3, 0.4, 0.5, 0.5, 0.4, 0.3]  # 1-lane ramp


def build():
    """Construct the freeway network and its demand; return the simulation."""
    upstream = Link(link_id=1, length=900, v_f=V_F, w=W, rho_jam=3 * RHO_JAM)
    transition = Link(link_id=2, length=150, v_f=V_F, w=W, rho_jam=3 * RHO_JAM)
    ramp = Link(link_id=3, length=300, v_f=V_F, w=W, rho_jam=RHO_JAM)
    downstream = Link(link_id=4, length=900, v_f=V_F, w=W, rho_jam=3 * RHO_JAM)

    mainline_trips = vehicles_from_demand_profile(MAINLINE, TOTAL_TIME, route=[1, 2, 4])
    ramp_trips = vehicles_from_demand_profile(RAMP, TOTAL_TIME, route=[3, 4])

    nodes = [
        OriginNode(node_id=1, link=upstream, demand_trips=mainline_trips),
        OriginNode(node_id=2, link=ramp, demand_trips=ramp_trips),
        OneToOneNode(node_id=3, inbound_link=upstream, outbound_link=transition),
        # 0.75 / 0.25 mainline:ramp merge priority -> circular vector [0,0,0,1].
        MergeNode(
            node_id=4,
            outbound_link=downstream,
            inbound_links=[transition, ramp],
            priority_vector=[0, 0, 0, 1],
        ),
        DestinationNode(node_id=5, link=downstream),
    ]

    links = [upstream, transition, ramp, downstream]
    return (
        Simulation(links=links, nodes=nodes, time_step=DT, total_time=TOTAL_TIME),
        links,
    )


def main() -> None:
    """Run the synthetic freeway-merge scenario and save the flow figure."""
    sim, links = build()
    sim.run()
    _upstream, transition, ramp, downstream = links
    print("Freeway merge (synthetic demand):")
    print(f"  mainline discharged: {transition.cumulative_outflows[-1]} veh")
    print(f"  ramp discharged:     {ramp.cumulative_outflows[-1]} veh")
    print(f"  downstream out:      {downstream.cumulative_outflows[-1]} veh")
    capacity = RHO_JAM * V_F * W / (V_F + W)
    print(
        f"  per-lane capacity ~ {capacity * 3600:.0f} veh/h "
        f"(3-lane ~ {capacity * 3 * 3600:.0f} veh/h)"
    )

    matplotlib.use("Agg")
    # A 3-panel overview: the merge topology (with each link's total throughput),
    # cumulative in/out per link, and per-link flow (veh/h) over time — so it is
    # clear which link carries which flow on this small network.
    names = ["upstream", "transition", "ramp", "downstream"]
    fig, axes = plt.subplots(1, 3, figsize=(17, 4.5))
    _draw_schematic(axes[0], links, names)
    plot_cumulative_curves(sim, ax=axes[1])
    axes[1].set_title("Cumulative in (solid) / out (dashed) per link")
    plot_link_flows(
        sim, [lk.link_id for lk in links], labels=names, window=120, ax=axes[2]
    )
    axes[2].set_title("Per-link flow over time")
    fig.tight_layout()
    print("Figure saved to", savefig(fig, "freeway_overview", subdir=SUBDIR))


# Fixed geometry of the on-ramp merge, used only to draw the schematic.
_SCHEMATIC_POS = {1: (0, 1), 3: (2, 1), 4: (3, 1), 5: (5, 1), 2: (2, 0)}
_SCHEMATIC_EDGES = [(1, 3, 0), (3, 4, 1), (2, 4, 2), (4, 5, 3)]  # (u, v, link index)


def _draw_schematic(ax, links, names) -> None:
    """Draw the on-ramp topology, labelling each link with its total throughput."""
    for u, v, idx in _SCHEMATIC_EDGES:
        pu, pv = _SCHEMATIC_POS[u], _SCHEMATIC_POS[v]
        ax.annotate(
            "",
            xy=pv,
            xytext=pu,
            arrowprops=dict(arrowstyle="->", lw=2.5, color="#4477aa"),
        )
        ax.annotate(
            f"{names[idx]}\n{links[idx].cumulative_outflows[-1]:.0f} veh",
            ((pu[0] + pv[0]) / 2, (pu[1] + pv[1]) / 2),
            fontsize=8,
            ha="center",
            va="center",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="0.7"),
        )
    for node, pos in _SCHEMATIC_POS.items():
        ax.scatter(*pos, s=320, color="white", edgecolors="black", zorder=3)
        ax.annotate(str(node), pos, ha="center", va="center", fontsize=8, zorder=4)
    ax.set_title("On-ramp merge topology (total throughput)")
    ax.set_aspect("equal")
    ax.margins(0.15)
    ax.axis("off")


if __name__ == "__main__":
    main()
