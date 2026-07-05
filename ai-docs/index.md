# mesoLTM (mesoltm) — overview for AI agents

mesoLTM is a **mesoscopic, individual-vehicle Link Transmission Model (LTM)** for
traffic flow on general road networks, distributed as the pip package `mesoltm`.
It advances a discrete LTM (triangular fundamental diagram per link, kinematic-wave
node flows) where **every unit of flow is one `Vehicle`** with its own mutable
route, metadata, and travel record. It is a faithful port of de Souza, Verbas,
Auld & Tampère, *"A mesoscopic link-transmission-model able to track individual
vehicles"*, Simulation Modelling Practice and Theory 140 (2025) 103088
(DOI 10.1016/j.simpat.2025.103088).

Requires **Python 3.11+**. Runtime dependencies: `numpy`, `networkx`. Optional
`[plot]` extra adds `matplotlib` for visualisation. License: AGPL-3.0-or-later.

## Install

```bash
pip install mesoltm            # core
pip install "mesoltm[plot]"    # + matplotlib for plots/animations
```

## Minimal example

Build a grid, add demand, run, count arrivals.

```python
from mesoltm import Vehicle, grid_network, ShortestPathPolicy

net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
net.set_origin((0, 0), vehicles=[
    Vehicle(vehicle_id=k, start=float(k), origin=(0, 0), destination=(3, 3))
    for k in range(50)
])
sim = net.compile(time_step=1.0, total_time=400.0,
                  routing_policy=ShortestPathPolicy(dynamic=True))
sim.run()
arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
```

## Public API map (import from `mesoltm`)

The top-level package re-exports the full public API:

```python
from mesoltm import (
    # links
    BaseLink, Link, ConnectorLink,
    # vehicle + loop
    Vehicle, Simulation,
    # nodes
    BaseNode, OneToOneNode, DivergeNode, MergeNode, GeneralNodeModel,
    OriginNode, DestinationNode,
    # network
    Network, NetworkState, VehicleView,
    grid_network, corridor_network, network_from_dict, network_to_dict, link_capacity,
    # routing
    RoutingPolicy, StaticRoutePolicy, ShortestPathPolicy,
    # plugins (per-step loop hooks)
    Plugin, FunctionPlugin, ReroutingPlugin,
    # demand + metrics
    vehicles_from_demand_profile,
    collect_trips, trip_record, summarize_trips, write_trips_csv,
    # animation history (matplotlib-free)
    SimulationHistory, Frame, AgentSnapshot, WaitingSnapshot, capture_frame, record_run,
)
```

Plotting/animation helpers are **not** in the top-level package; import them from
`mesoltm.visualizations` (needs `[plot]`). See [visualization.md](visualization.md).

## Topic files

- [installation.md](installation.md) — install, extras, Python version, ffmpeg.
- [quickstart.md](quickstart.md) — grid, corridor, CLI, reading results.
- [model.md](model.md) — FD symbols, equations, four-phase loop, node algorithms.
- [networks.md](networks.md) — `Network` builder, grid/corridor, dict I/O.
- [vehicles-and-routing.md](vehicles-and-routing.md) — `Vehicle`, routing policies.
- [plugins.md](plugins.md) — per-step hooks, `ReroutingPlugin`.
- [simulation.md](simulation.md) — run/start/step/inject, `NetworkState`.
- [metrics.md](metrics.md) — trip records and summaries.
- [visualization.md](visualization.md) — plots, animations, recording.
- [scenarios-cli.md](scenarios-cli.md) — JSON scenario schema and CLI.
- [api-reference.md](api-reference.md) — condensed signatures of every public symbol.
- [gotchas.md](gotchas.md) — common pitfalls and constraints.

## Citation

TODO: a DOI has **not** yet been registered for this repository. Placeholder:

```bibtex
@software{mesoltm,
  author  = {Schlapbach, Julius},
  title   = {{mesoLTM}: a mesoscopic (individual-vehicle) Link Transmission Model},
  version = {0.1.0},
  url     = {https://github.com/sjschlapbach/mesoLTM},
  note    = {TODO: DOI pending registration (e.g. via Zenodo)},
  year    = {2026}
}
```

Also cite the paper (DOI 10.1016/j.simpat.2025.103088).
