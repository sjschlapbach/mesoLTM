# mesoLTM

**A mesoscopic, individual-vehicle Link Transmission Model for traffic flow on
general road networks — distributed as the pip package `mesoltm`.**

`mesoltm` sits in the middle of the traffic-modelling spectrum. **Microscopic**
models resolve car-following and lane-changing for every vehicle; **macroscopic**
models track only aggregate density and flow along links. A **mesoscopic** model
keeps the computational thrift of the macroscopic world while still following
*individual vehicles* — here, the discrete Link Transmission Model (LTM) advances
a triangular fundamental diagram on each link, but every unit of flow is one
vehicle with its own identity, route, and travel record.

That combination is what makes `mesoltm` useful: it scales to whole networks, yet
each vehicle carries a **mutable, per-vehicle route** you can rewrite mid-run
(for dynamic routing, access control, or reactive rerouting), plus free-form
metadata and a full trajectory for post-hoc analysis.

`mesoltm` is a re-implementation of the discrete LTM of de Souza, Verbas, Auld &
Tampère.[^paper] It builds on their work, keeping the core traffic-flow
mathematics and adding general-network topologies, per-vehicle routing, plugins,
and trip metrics on top; every deliberate change is catalogued in
[Deviations from the paper](model/deviations-from-the-paper.md).

## Install

```bash
pip install mesoltm            # core (numpy + networkx)
pip install "mesoltm[plot]"    # + matplotlib for plots and animations
```

Requires **Python 3.11+**. See [Installation](getting-started/installation.md) for
all extras.

## Quick start

```python
from mesoltm import Vehicle, grid_network, ShortestPathPolicy

# A 4x4 grid where every node can be an origin or a destination.
net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
net.set_origin((0, 0), vehicles=[
    Vehicle(vehicle_id=k, scheduled_departure=float(k), origin=(0, 0), destination=(3, 3))
    for k in range(50)
])

sim = net.compile(time_step=1.0, total_time=400.0,
                  routing_policy=ShortestPathPolicy(dynamic=True))
sim.run()
print(sum(len(n.get_arrived_trips()) for n in sim.nodes), "vehicles arrived")
```

Continue with the [Quickstart](getting-started/quickstart.md), or run a JSON
scenario straight from the command line — see
[Running a scenario](getting-started/running-a-scenario.md).

## Where to go next

<div class="grid cards" markdown>

- :material-book-open-variant: **[The Model](model/overview.md)** — the discrete
  LTM, the fundamental diagram, node flow resolution, and the simulation loop.
- :material-tools: **[User Guide](guide/building-networks.md)** — building
  networks, routing, plugins, metrics, and visualisation.
- :material-api: **[API Reference](reference/index.md)** — auto-generated from the
  source docstrings.
- :material-scale-balance: **[About](about/citation.md)** — how to cite `mesoltm`,
  license, and changelog.

</div>

!!! note "Citing mesoLTM"
    If you use `mesoltm` in academic or other work, please cite this repository.
    A DOI is **not yet registered** — see [Citation](about/citation.md) for the
    current placeholder entry.

[^paper]: F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, *"A mesoscopic
    link-transmission-model able to track individual vehicles"*, Simulation
    Modelling Practice and Theory **140** (2025) 103088.
    DOI: [10.1016/j.simpat.2025.103088](https://doi.org/10.1016/j.simpat.2025.103088).
