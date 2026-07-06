"""Reproduce the paper's validation scenarios with the mesoltm pipeline.

This single script re-runs the validation experiments of

    F. de Souza, O. Verbas, J. Auld, C. M. J. Tampere, "A mesoscopic
    link-transmission-model able to track individual vehicles", Simulation
    Modelling Practice and Theory 140 (2025) 103088.
    https://doi.org/10.1016/j.simpat.2025.103088

and redraws the corresponding figures using only the shipped ``mesoltm``
package, so the pipeline can be checked against the original formulation.

Reproduced figures (Section 4 of the paper):

  * Fig. 5  -- Section 4.1  lane-drop (one-to-one), dt = 1 / 3 / 6 s
  * Fig. 6  -- Section 4.1  lane-drop with W = 7 m/s, dt = 2 / 4 s
  * Fig. 7  -- Section 4.2  diverge, beta = 0.75 / 0.25, dt = 1 / 3 s
  * Fig. 8  -- Section 4.2  diverge with random route draws (replications)
  * Fig. 9  -- Section 4.3  merge, two priority settings, dt = 1 s

Deliberate differences from the paper (see the "Deviations from the paper" docs
page, ``docs/model/deviations-from-the-paper.md``); these are
scope choices of ``mesoltm``, not discrepancies in the ported dynamics:

  * **No continuous-LTM reference.** ``mesoltm`` ships only the discrete model,
    so the paper's grey continuous curves are not drawn. Where the paper's panels
    (c)/(d) show the *error vs. the continuous LTM*, this script instead shows the
    *deviation from the finest discrete run* (dt = 1 s) -- a computable, discrete-
    only convergence check that carries the same "bounded, step-dependent error"
    message.
  * **Fig. 5, dt = 6 s is rejected.** With L = 150 m and V = 30 m/s the CFL
    condition (max(V, W) * dt <= L) is violated at dt = 6 s (180 > 150). ``abmmeso``
    silently floors the wave lag and runs anyway; ``mesoltm`` raises a
    ``ValueError`` on purpose (Deviations page, A7). The script catches it and marks
    the curve as rejected rather than plotting a mis-discretised result.
  * **Fig. 6 shows the proposed model only.** The paper also plots a constant
    ``floor(C*dt)`` capacity ablation (``noCapacityStateVarLink``); ``mesoltm``
    intentionally did not port that variant, so it is omitted.
  * **Figs. 11 and 12 are not reproduced.** The permitted/protected signal (Fig.
    11) needs a signalised node model that ``mesoltm`` does not implement, and the
    real-world US-101 case (Fig. 12) needs PeMS field data and a continuous-LTM
    calibration that are not part of this package.

Run: ``python examples/paper_validation.py``
"""

from __future__ import annotations

import pathlib
import random
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import (  # noqa: E402
    DestinationNode,
    DivergeNode,
    Link,
    MergeNode,
    OneToOneNode,
    OriginNode,
    Simulation,
    vehicles_from_demand_profile,
)

SUBDIR = pathlib.Path(__file__).stem  # figures -> output/paper_validation/

# Fundamental-diagram constants shared by the paper's validation networks.
V_F = 30.0  # free-flow speed [m/s]
W = 6.0  # backward shock-wave speed [m/s]
LENGTH = 150.0  # link length [m]

# Colours: time-step curves (Figs 5/6) and per-link roles (Figs 7-9).
DT_COLORS = {1: "#d7191c", 3: "#2c7bb6", 6: "#fdae61", 2: "#e75480", 4: "#2c7bb6"}
UPSTREAM = "#7b3294"  # purple  -- upstream / main approach
DOWN_1 = "#2c7fb8"  # light blue -- first downstream / second upstream
DOWN_2 = "#e66101"  # orange  -- second downstream


# --------------------------------------------------------------------------- #
# Small extraction helpers (analysis only -- NumPy never touches the core loop) #
# --------------------------------------------------------------------------- #
def cum_curve(link, dt: float):
    """Return (times, cumulative array) for a link's per-step cumulative counts."""
    times = dt * np.arange(len(link.cumulative_inflows))
    return times, np.asarray(link.cumulative_inflows, dtype=float)


def step_flow(cumulative, dt: float):
    """Per-step flow (veh per step) and its left-edge times from a cumulative list."""
    cum = np.asarray(cumulative, dtype=float)
    return dt * np.arange(len(cum) - 1), np.diff(cum)


def deviation_from_baseline(link, dt, base_link, base_dt, attr):
    """Deviation of a coarse run's cumulative curve from the dt=1 s baseline.

    Both curves are read at the coarse run's time points (the baseline is
    interpolated onto them), giving the discrete-only analogue of the paper's
    "error vs. continuous" panels.
    """
    coarse = np.asarray(getattr(link, attr), dtype=float)
    coarse_t = dt * np.arange(len(coarse))
    base = np.asarray(getattr(base_link, attr), dtype=float)
    base_t = base_dt * np.arange(len(base))
    return coarse_t, coarse - np.interp(coarse_t, base_t, base)


# --------------------------------------------------------------------------- #
# Scenario builders (direct attachment, exactly as the paper -- no connectors)  #
# --------------------------------------------------------------------------- #
def run_lane_drop(rho_up, rho_down, w, demand, demand_time, dt, sim_time):
    """Two successive links (lane drop); return (upstream, downstream) links."""
    l1 = Link(link_id=1, length=LENGTH, rho_jam=rho_up, w=w, v_f=V_F)
    l2 = Link(link_id=2, length=LENGTH, rho_jam=rho_down, w=w, v_f=V_F)
    trips = vehicles_from_demand_profile(demand, demand_time, route=[1, 2])
    nodes = [
        OriginNode(node_id=0, link=l1, demand_trips=trips),
        OneToOneNode(node_id=1, inbound_link=l1, outbound_link=l2),
        DestinationNode(node_id=2, link=l2),
    ]
    Simulation(links=[l1, l2], nodes=nodes, time_step=dt, total_time=sim_time).run()
    return l1, l2


def run_diverge(dt, sim_time, random_route=False, seed=None):
    """One upstream link diverging (FIFO, 3:1 route split) into two links."""
    if seed is not None:
        random.seed(seed)
    l1 = Link(link_id=1, length=LENGTH, rho_jam=0.2, w=W, v_f=V_F)
    l2 = Link(link_id=2, length=LENGTH, rho_jam=0.1, w=W, v_f=V_F)
    l3 = Link(link_id=3, length=LENGTH, rho_jam=0.1, w=W, v_f=V_F)
    # d = 0.8 veh/s for t < 50 s, 0.4 veh/s for 50 < t <= 120 s (10 s slices).
    demand = [0.8] * 5 + [0.4] * 7
    trips = vehicles_from_demand_profile(
        demand,
        120.0,
        route_integer_share={(1, 2): 3, (1, 3): 1},
        random_route=random_route,
    )
    nodes = [
        OriginNode(node_id=0, link=l1, demand_trips=trips),
        DivergeNode(node_id=1, inbound_link=l1, outbound_links=[l2, l3]),
        DestinationNode(node_id=2, link=l2),
        DestinationNode(node_id=3, link=l3),
    ]
    Simulation(links=[l1, l2, l3], nodes=nodes, time_step=dt, total_time=sim_time).run()
    return l1, l2, l3


def run_merge(priority_vector, dt, sim_time):
    """Two upstream links merging into one, with the given inbound priority vector."""
    l1 = Link(link_id=1, length=LENGTH, rho_jam=0.1, w=W, v_f=V_F)
    l2 = Link(link_id=2, length=LENGTH, rho_jam=0.1, w=W, v_f=V_F)
    l3 = Link(link_id=3, length=LENGTH, rho_jam=0.1, w=W, v_f=V_F)
    # d1 = 0.3 for all t; d2 = 0.3 for t < 40 s then 0.1 (20 s slices, 0..120 s).
    trips1 = vehicles_from_demand_profile([0.3] * 6, 120.0, route=[1, 3], origin=1)
    trips2 = vehicles_from_demand_profile(
        [0.3, 0.3, 0.1, 0.1, 0.1, 0.1], 120.0, route=[2, 3], origin=2
    )
    nodes = [
        OriginNode(node_id=0, link=l1, demand_trips=trips1),
        OriginNode(node_id=1, link=l2, demand_trips=trips2),
        MergeNode(
            node_id=2,
            outbound_link=l3,
            inbound_links=[l1, l2],
            priority_vector=priority_vector,
        ),
        DestinationNode(node_id=3, link=l3),
    ]
    Simulation(links=[l1, l2, l3], nodes=nodes, time_step=dt, total_time=sim_time).run()
    return l1, l2, l3


# --------------------------------------------------------------------------- #
# Figure 5 / 6 -- lane-drop (one-to-one)                                        #
# --------------------------------------------------------------------------- #
def lane_drop_figure(rho_up, rho_down, w, demand, demand_time, dts, title, fname):
    """Six-panel lane-drop figure (paper Figs 5/6) for the given time steps.

    dt = 1 s is always run as the deviation baseline for panels (c)/(d), even if
    it is not in ``dts``.
    """
    sim_time = 300.0
    runs, rejected = {}, []
    for dt in sorted(set(dts) | {1}):
        try:
            runs[dt] = run_lane_drop(
                rho_up, rho_down, w, demand, demand_time, dt, sim_time
            )
        except ValueError as exc:  # CFL guard (deliberate; Deviations page, A7)
            rejected.append(dt)
            print(f"    dt = {dt} s rejected by CFL guard: {exc}".replace("\n", " "))
    base_up, base_down = runs[1]

    fig, axes = plt.subplots(2, 3, figsize=(16, 8.5))
    fig.suptitle(title, fontsize=13)
    a, b, c, d, e, f = axes.flat

    for dt in dts:
        if dt not in runs:
            continue
        up, down = runs[dt]
        colour = DT_COLORS[dt]
        label = f"discrete dt = {dt} s"

        t_in, cum_in = cum_curve(up, dt)
        cum_out = np.asarray(up.cumulative_outflows, dtype=float)
        a.plot(t_in, cum_in, color=colour, label=f"{label} (F)")
        a.plot(t_in, cum_out, color=colour, ls="--", label=f"{label} (G)")

        b.plot(t_in, cum_in - cum_out, color=colour, label=label)

        tc, dev_in = deviation_from_baseline(up, dt, base_up, 1, "cumulative_inflows")
        c.plot(tc, dev_in, color=colour, label=label)
        td, dev_out = deviation_from_baseline(
            down, dt, base_down, 1, "cumulative_outflows"
        )
        d.plot(td, dev_out, color=colour, label=label)

        te, in_flow = step_flow(up.cumulative_inflows, dt)
        e.step(te, in_flow, where="post", color=colour, label=label)
        tf, out_flow = step_flow(up.cumulative_outflows, dt)
        f.step(tf, out_flow, where="post", color=colour, label=label)

    a.set(
        title="(a) link 1 cumulative flows: F (solid), G (dashed)",
        xlabel="time [s]",
        ylabel="cumulative vehicles",
    )
    b.set(title="(b) vehicles in link 1  (F - G)", xlabel="time [s]", ylabel="vehicles")
    c.set(
        title="(c) link 1 cumulative-inflow deviation vs dt = 1 s",
        xlabel="time [s]",
        ylabel="vehicles",
    )
    d.set(
        title="(d) link 2 cumulative-outflow deviation vs dt = 1 s",
        xlabel="time [s]",
        ylabel="vehicles",
    )
    e.set(
        title="(e) link 1 inflow per step", xlabel="time [s]", ylabel="vehicles / step"
    )
    f.set(
        title="(f) link 1 outflow per step", xlabel="time [s]", ylabel="vehicles / step"
    )
    for ax in axes.flat:
        ax.legend(fontsize=7)
        ax.grid(alpha=0.3)
    if rejected:
        fig.text(
            0.5,
            0.005,
            "dt = "
            + ", ".join(f"{r} s" for r in rejected)
            + " rejected by the CFL guard (deliberate; see Deviations page, A7)",
            ha="center",
            fontsize=9,
            style="italic",
            color="#b2182b",
        )
    fig.tight_layout(rect=(0, 0.02, 1, 0.97))

    # Pipeline check: discretisation deviation stays bounded (~1 vehicle).
    max_dev = 0.0
    for dt in dts:
        if dt in runs and dt != 1:
            _, dev = deviation_from_baseline(
                runs[dt][0], dt, base_up, 1, "cumulative_inflows"
            )
            max_dev = max(max_dev, float(np.abs(dev).max()))
    print(f"    max cumulative deviation vs dt = 1 s: {max_dev:.2f} veh")
    print("    figure ->", savefig(fig, fname, subdir=SUBDIR))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 7 -- diverge                                                          #
# --------------------------------------------------------------------------- #
def diverge_figure():
    """Two-row diverge figure (paper Fig 7): dt = 1 s (top), dt = 3 s (bottom)."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle(
        "Fig. 7 - diverge, beta1 = 0.75 / beta2 = 0.25 (3:1 route split)", fontsize=13
    )
    for row, dt in enumerate((1, 3)):
        l1, l2, l3 = run_diverge(dt, 200.0)
        left, mid, right = axes[row]

        t, _ = cum_curve(l1, dt)
        left.plot(t, l1.cumulative_outflows, color=UPSTREAM, label="upstream out (G1)")
        left.plot(t, l2.cumulative_inflows, color=DOWN_1, label="link 1 in (F2)")
        left.plot(t, l3.cumulative_inflows, color=DOWN_2, label="link 2 in (F3)")
        left.set(
            title=f"(dt = {dt} s) cumulative flows",
            xlabel="time [s]",
            ylabel="cumulative vehicles",
        )

        tm, flow2 = step_flow(l2.cumulative_inflows, dt)
        mid.step(tm, flow2, where="post", color=DOWN_1)
        mid.set(
            title=f"(dt = {dt} s) flow into link 1",
            xlabel="time [s]",
            ylabel="vehicles / step",
        )

        tr, flow3 = step_flow(l3.cumulative_inflows, dt)
        right.step(tr, flow3, where="post", color=DOWN_2)
        right.set(
            title=f"(dt = {dt} s) flow into link 2",
            xlabel="time [s]",
            ylabel="vehicles / step",
        )

        share = l2.cumulative_inflows[-1] / max(1, l1.cumulative_outflows[-1])
        print(f"    dt = {dt} s: link-1 share = {share:.3f} (target 0.75)")
        for ax in axes[row]:
            ax.grid(alpha=0.3)
        left.legend(fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    print("    figure ->", savefig(fig, "fig07_diverge", subdir=SUBDIR))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 8 -- diverge with random route draws                                  #
# --------------------------------------------------------------------------- #
def diverge_random_figure(n_replications=20):
    """Random-draw diverge (paper Fig 8): replications enveloping the 3:1 reference."""
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.suptitle(
        "Fig. 8 - diverge with random route draws (P = 0.75 / 0.25), dt = 1 s",
        fontsize=12,
    )
    dt = 1.0

    for k in range(n_replications):
        l1, l2, l3 = run_diverge(dt, 200.0, random_route=True, seed=k)
        t, _ = cum_curve(l1, dt)
        lbl = "replications" if k == 0 else None
        ax.plot(t, l1.cumulative_inflows, color=UPSTREAM, alpha=0.18, lw=0.8, label=lbl)
        ax.plot(t, l2.cumulative_inflows, color=DOWN_1, alpha=0.18, lw=0.8)
        ax.plot(t, l3.cumulative_inflows, color=DOWN_2, alpha=0.18, lw=0.8)

    # Deterministic 3:1 reference (bold), as in the paper.
    r1, r2, r3 = run_diverge(dt, 200.0, random_route=False)
    t, _ = cum_curve(r1, dt)
    ax.plot(t, r1.cumulative_inflows, color=UPSTREAM, lw=2.2, label="upstream (ref)")
    ax.plot(t, r2.cumulative_inflows, color=DOWN_1, lw=2.2, label="link 1 (ref)")
    ax.plot(t, r3.cumulative_inflows, color=DOWN_2, lw=2.2, label="link 2 (ref)")

    ax.set(xlabel="time [s]", ylabel="cumulative inflow [vehicles]")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    print(f"    {n_replications} random replications enveloping the 3:1 reference")
    print("    figure ->", savefig(fig, "fig08_diverge_random", subdir=SUBDIR))
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Figure 9 -- merge                                                            #
# --------------------------------------------------------------------------- #
def merge_figure():
    """Two-row merge figure (paper Fig 9): equal vs. 3:1 inbound priority, dt = 1 s."""
    settings = [
        ([0, 1], "alpha1 = 0.50, x = [0, 1]"),
        ([0, 0, 0, 1], "alpha1 = 0.75, x = [0, 0, 0, 1]"),
    ]
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle("Fig. 9 - merge for two priority settings, dt = 1 s", fontsize=13)
    dt = 1.0
    for row, (pvec, label) in enumerate(settings):
        l1, l2, l3 = run_merge(pvec, dt, 200.0)
        left, mid, right = axes[row]

        t, _ = cum_curve(l1, dt)
        left.plot(t, l1.cumulative_outflows, color=UPSTREAM, label="link 1 out (G1)")
        left.plot(t, l2.cumulative_outflows, color=DOWN_1, label="link 2 out (G2)")
        left.plot(t, l3.cumulative_inflows, color=DOWN_2, label="downstream in (Fd)")
        left.set(
            title=f"({label}) cumulative flows",
            xlabel="time [s]",
            ylabel="cumulative vehicles",
        )

        tm, flow1 = step_flow(l1.cumulative_outflows, dt)
        mid.step(tm, flow1, where="post", color=UPSTREAM)
        mid.set(
            title="outflow from link 1", xlabel="time [s]", ylabel="vehicles / step"
        )

        tr, flow2 = step_flow(l2.cumulative_outflows, dt)
        right.step(tr, flow2, where="post", color=DOWN_1)
        right.set(
            title="outflow from link 2", xlabel="time [s]", ylabel="vehicles / step"
        )

        # Priority only shifts the transient during congestion (t < 40 s); the
        # final totals are demand-limited and identical across settings. Report the
        # share discharged within the congested window, where priority bites.
        g1, g2 = l1.cumulative_outflows[40], l2.cumulative_outflows[40]
        share1 = g1 / max(1, g1 + g2)
        print(
            f"    {label}: link-1 share at t=40 s = {share1:.3f} " f"(G1={g1}, G2={g2})"
        )
        for ax in axes[row]:
            ax.grid(alpha=0.3)
        left.legend(fontsize=7)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    print("    figure ->", savefig(fig, "fig09_merge", subdir=SUBDIR))
    plt.close(fig)


def main() -> None:
    """Run every reproduced scenario and save one figure per paper figure."""
    matplotlib.use("Agg")

    print("Fig. 5 - lane-drop one-to-one (C1 = 1.0, C2 = 0.5 veh/s):")
    lane_drop_figure(
        rho_up=0.2,
        rho_down=0.1,
        w=6.0,
        demand=[1.0, 0.2, 0.2],
        demand_time=150.0,
        dts=[1, 3, 6],
        title="Fig. 5 - lane-drop (one-to-one), W = 6 m/s",
        fname="fig05_lane_drop",
    )

    print("Fig. 6 - lane-drop with W = 7 m/s (C1 = 1.14, C2 = 0.57 veh/s):")
    lane_drop_figure(
        rho_up=0.2,
        rho_down=0.1,
        w=7.0,
        demand=[1.0, 0.2, 0.2],
        demand_time=150.0,
        dts=[2, 4],
        title="Fig. 6 - lane-drop, W = 7 m/s (proposed model only)",
        fname="fig06_lane_drop_w7",
    )

    print("Fig. 7 - diverge:")
    diverge_figure()

    print("Fig. 8 - diverge with random route draws:")
    diverge_random_figure()

    print("Fig. 9 - merge:")
    merge_figure()

    print(f"\nAll figures written to examples/output/{SUBDIR}/")


if __name__ == "__main__":
    main()
