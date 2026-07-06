# Model overview

`mesoltm` implements the **discrete, individual-vehicle Link Transmission Model
(LTM)** of de Souza, Verbas, Auld & Tampère.[^paper] This page gives the mental
model; the following pages fill in the fundamental diagram, the node models, and
the time loop.

## Where a mesoscopic model sits

| | Microscopic | **Mesoscopic (this model)** | Macroscopic |
|---|---|---|---|
| Unit tracked | individual vehicles + interactions | **individual vehicles** | aggregate density/flow |
| Dynamics | car-following, lane-changing | **link fundamental diagram**, node flow resolution | continuum (LWR/CTM) |
| Cost | high | **low–medium** | low |
| Per-vehicle routes/metrics | yes | **yes** | no |

The LTM is normally a *macroscopic* method: it advances the cumulative number of
vehicles that have entered and left each link, using only the link's fundamental
diagram and the kinematic-wave travel times. The **mesoscopic** twist here is that
every unit of flow is one `Vehicle` object with an identity and a route, so the
model keeps LTM's efficiency while letting you follow, reroute, and measure each
vehicle.

## The two ingredients

**Links** carry a triangular fundamental diagram. Each step, a link offers a
**sending flow** (demand — how many vehicles are ready to leave its downstream
end) and a **receiving flow** (supply — how many it can accept at its upstream
end). These are computed from the cumulative in/outflow curves lagged by the
forward and backward wave travel times, then floored to whole vehicles and capped
by an integer capacity budget. See [Links & the fundamental diagram](links-and-fd.md).

**Nodes** resolve competing demands and supplies into actual integer flows. A
one-to-one node just passes vehicles along; a diverge splits a stream FIFO; a
merge shares scarce downstream supply by priority; the general node model handles
arbitrary many-to-many junctions with outbound locking. See
[Nodes & flow resolution](nodes.md).

## Discreteness matters

Because one unit of flow is one vehicle, all node flows are **integer**. The model
achieves this with an integer *capacity-token* recursion on each link (a token
bucket that replenishes by `capacity · dt` each step and is debited by the actual
flow). This is what lets the continuous LTM be advanced vehicle-by-vehicle without
drift — and it follows the reference implementation's arithmetic and ordering.

## What runs each step

The engine repeats a fixed **four-phase loop**: plugins act → nodes prepare →
links compute demand/supply → nodes move vehicles → links commit. The ordering is
significant and is covered in [The simulation loop](simulation-loop.md).

Everything `mesoltm` *adds* — general-graph networks with connector links,
pluggable routing, per-step plugins, step-driven injection, metrics, and
visualisation — sits *around* that core traffic-flow model. Every change relative
to the reference is listed in
[Deviations from the paper](deviations-from-the-paper.md).

[^paper]: F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, *"A mesoscopic
    link-transmission-model able to track individual vehicles"*, Simulation
    Modelling Practice and Theory **140** (2025) 103088.
    DOI: [10.1016/j.simpat.2025.103088](https://doi.org/10.1016/j.simpat.2025.103088).
