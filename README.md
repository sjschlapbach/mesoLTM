# mesoLTM

[![DOI](https://zenodo.org/badge/1288132632.svg)](https://doi.org/10.5281/zenodo.21443220)
[![PyPI Version](https://img.shields.io/pypi/v/mesoltm)](https://pypi.org/project/mesoltm/)
[![Package Build](https://github.com/sjschlapbach/mesoLTM/actions/workflows/build.yml/badge.svg)](https://github.com/sjschlapbach/mesoLTM/actions/workflows/build.yml)
[![Python Types](https://github.com/sjschlapbach/mesoLTM/actions/workflows/typecheck.yml/badge.svg)](https://github.com/sjschlapbach/mesoLTM/actions/workflows/typecheck.yml)
[![Python Tests](https://github.com/sjschlapbach/mesoLTM/actions/workflows/test.yml/badge.svg)](https://github.com/sjschlapbach/mesoLTM/actions/workflows/test.yml)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)

A **mesoscopic (individual-vehicle) Link Transmission Model** for traffic flow on
general road networks, distributed as the pip package `mesoltm`.

`mesoltm` implements the discrete LTM of de Souza, Verbas, Auld & Tampère — a
computationally efficient macroscopic-style model that nonetheless **tracks every
vehicle individually**, so each vehicle carries its own (re-routable) path. It runs
on arbitrary graphs and grids, supports parallel links (fast/slow lanes and
detours), and exposes clean interfaces for external routing and per-step
simulation plugins.

**Full documentation:** [https://sjschlapbach.github.io/mesoLTM](https://sjschlapbach.github.io/mesoLTM/) \
**Python Package:** [https://pypi.org/project/mesoltm](https://pypi.org/project/mesoltm/)

## Requirements

- Python **3.11+**

## Install

```bash
pip install mesoltm
```

For plotting support, install the `plot` extra:

```bash
pip install "mesoltm[plot]"
```

### From source (editable, for development)

```bash
python3.11 -m venv venv && source venv/bin/activate
pip install -e ".[dev,plot]"     # core + dev tooling + plotting
```

Extras: `plot` (matplotlib visualisations), `ui` (network editor, optional),
`calib` (scipy, for calibration examples), `dev` (pytest, pylint, black, mypy, build).

## Quick Start

```python
from mesoltm import Vehicle, grid_network, ShortestPathPolicy

# A 4x4 grid where every node can be an origin or a destination.
net = grid_network(4, 4, link_length=200.0, all_nodes_od=True)
net.set_origin((0, 0), vehicles=[
    Vehicle(vehicle_id=k, start=float(k), origin=(0, 0), destination=(3, 3))
    for k in range(50)
])

sim = net.compile(time_step=1.0, total_time=400.0,
                  routing_policy=ShortestPathPolicy(dynamic=True))
sim.run()
print(sum(len(n.get_arrived_trips()) for n in sim.nodes), "vehicles arrived")
```

Or run a JSON scenario from the command line:

```bash
python -m mesoltm examples/scenario.json     # writes link/trip CSVs
```

## Examples

Executable scripts under [`examples/`](examples) (run with `python examples/<name>.py`).
Each writes its figures (and any CSVs) to its own subdirectory
`examples/output/<script_name>/`, so results are easy to tell apart.

- `freeway_onramp.py` — a freeway on-ramp merge on a calibrated topology with a
  synthetic demand profile.
- `grid_demo.py` — a partial grid with shortest-path routing.
- `rerouting_demo.py` — manual per-vehicle rerouting: dynamic routing is off
  (static route-following), and a plugin hand-picks specific vehicles and rewrites
  their routes onto a detour mid-run (no closed links, no shortest-path search).
- `adaptive_rerouting_intersection.py` — the most basic 2-in/2-out uncontrolled
  ("no-way-stop") intersection (a general node); agents are re-checked every step
  against the live shortest path from their current link onward (no U-turns),
  reroutes are versioned, and a few agents' initial-vs-final plans are plotted.
- `parallel_links_demo.py` — fast lane, slow lane and an inflated-length detour,
  run twice: free-flow routing (everyone piles on the fast lane until it closes)
  vs congestion-aware routing (a cost that grows with each link's load spreads
  traffic onto the slow lane and detour).
- `vehicle_metrics_demo.py` — collect per-vehicle travel times (overall and per
  link) with `mesoltm.metrics` and plot the travel-time distribution, per-link
  means, and a per-link travel-time time series showing congestion building up.
- `bottleneck_access_policy.py` — a **random bottleneck access policy** driven with
  `Simulation.start`/`step`/`inject`: vehicles are released toward a goal via a fast
  **bottleneck**, and a `ReroutingPlugin` tosses a coin as each one approaches to
  admit it or divert it onto a slower parallel path (one toss per access). Plots each
  of four vehicles' route before the toss, after it, and as actually driven, and
  records the run as a **video** (plus per-step frames) of the vehicles moving
  link-to-link — blue while planning the bottleneck, then green (admitted) or orange
  (diverted).
- `congestion_aware_routing.py` — a `ReroutingPlugin` that balances a burst of
  traffic across a short and a long route using a shortest-path cost that combines
  link length (free-flow time) with current load (`state.occupancy`).
- `grid_visualization.py` — grids under congestion-aware **route-based** rerouting: a
  `DensityRerouter` plugin re-plans each vehicle (shortest path on free-flow time + a
  linear density penalty) at every node and writes the plan onto `vehicle.route`, so
  the recorded log is exactly the route that ran. Two scenarios: a tiny **2x2 grid**
  (few vehicles, short horizon) whose per-step PNGs + JSON log can be checked by hand,
  and a dense **7x7 grid** (with holes) carrying many vehicles between random OD pairs.
  Each records a **video** of the agents moving, coloured by the link each takes next —
  showing the animation stays readable on a dense scenario (sizes scale to the network,
  per-agent detail auto-drops but is available on request). One still is coloured by a
  **custom function of each vehicle's `props` metadata** (a vehicle class) to show
  `color_by` is fully overridable.

## Key Concepts

- **Network** builder (`mesoltm.Network`, `grid_network`, `corridor_network`):
  add nodes/links, mark any node an origin/destination, `compile()` to a simulation.
- **Routing** (`RoutingPolicy`): per-vehicle, mutable mid-run; `StaticRoutePolicy`
  (follow `vehicle.route`) or `ShortestPathPolicy`, or your own.
- **Plugins** (`Plugin`): per-step loop hooks that run first each step to inspect
  `NetworkState` and change the simulation — reroute vehicles (each vehicle carries
  its own `route`, which the network merely propagates), gate/close links, run
  dispatchers or local auctions. `ReroutingPlugin` is the minimal rerouting form.
- **Visualisations** (`mesoltm.visualizations`, needs `[plot]`): cumulative curves,
  flow over time (`plot_link_flow` sums links into a cut; `plot_link_flows` draws
  one labelled line per link), per-link travel time over time
  (`plot_link_time_series`, to see congestion build up), and network maps
  (`plot_network`, colour links by flow/occupancy/…, optionally label each link and
  fan out parallel links).
- **Movement video** (`mesoltm.visualizations` + `record_history=True`): capture a
  per-step history (`Network.compile(record_history=True[, history_path=…])`, off by
  default; exposed as `Simulation.history`, JSON-serialisable) and render it to an
  MP4/GIF (`save_animation`, default 25 fps, `subsample` sets playback speed) and/or
  per-step PNGs (`save_frames`) of agents moving link-to-link — with next-link cues
  and a count badge on each node for agents waiting to enter. `color_by` chooses what
  a dot's colour means: `"category"`, `"next_link"`, `None` (uniform), or a **custom
  callable** `fn(snapshot) -> str` colouring by anything on the snapshot — most usefully
  each vehicle's free-form `Vehicle(props=…)` metadata, which travels with the vehicle
  and round-trips through the log. The log records each agent's remaining route straight
  from `vehicle.route` (never recomputed), so it always matches the simulation. The
  saved JSON log is self-describing (each agent/waiting entry is a keyed object). Scales
  from a small bottleneck to a dense grid.

## Development

```bash
pytest                        # tests (includes a numeric regression vs. the reference)
pylint src/mesoltm examples   # lint
black --check src examples    # format check
mypy src                      # types
python -m build               # sdist + wheel
```

`venv/` and build artefacts are git-ignored.

## Release

Releases are automated. Pushing a `v*.*.*` tag triggers the
[`release`](.github/workflows/release.yml) workflow, which validates versions,
generates the changelog with [git-cliff](https://git-cliff.org/) (config in
[`cliff.toml`](cliff.toml)), builds the distribution, publishes to PyPI, and creates
a GitHub Release. The changelog is derived from
[conventional commit](https://www.conventionalcommits.org) messages, so nothing in
`CHANGELOG.md` needs to be edited by hand. Make sure all tests and builds are passing,
then follow these steps.

#### 0. Prerequisites (important!)

Switch to `master` and make sure it has all the changes that should be in the release:

```bash
git checkout master
git pull origin master
```

You also need permission to push tags, and a `PYPI_TOKEN` repository secret must be
configured (a PyPI API token) for the publish step.

#### 1. Update the version in `pyproject.toml`

Set the `version` in `pyproject.toml` to the next release version according to the
conventional-commit history. To see what git-cliff computes as the next version, run:

```bash
git-cliff --bump --unreleased
```

⚠️ **Do not commit any `CHANGELOG.md` changes** — the release workflow regenerates and
commits the changelog automatically. Commit **only** the version bump in
`pyproject.toml`. If the `pyproject.toml` version and the git-cliff-computed version
disagree, the release workflow fails.

#### 2. Commit the version change

```bash
git checkout master                     # safeguard: ensure you are on master
git commit -m "chore(release): v0.1.0"  # replace v0.1.0 with the release version
git push origin master
```

#### 3. Create and push the tag (this triggers the workflow)

```bash
git checkout master                                   # safeguard: ensure you are on master
git tag -a v0.1.0 -m "chore(release): version 0.1.0"  # replace v0.1.0 with the release version
git push origin v0.1.0                                # push the tag to trigger the release workflow
```

#### 4. GitHub Actions then automatically

- Validates that the tag, `pyproject.toml`, changelog, and built wheel all agree on the version
- Generates `CHANGELOG.md` with git-cliff and commits it back to `master`
- Builds the sdist and wheel
- Publishes to PyPI
- Creates a GitHub Release with the changelog notes

## Attribution and Citation

**If you use `mesoltm` in academic or other work, please cite this repository.**
A machine-readable entry is provided in [`CITATION.cff`](CITATION.cff):

> J. Schlapbach, _mesoLTM: A Mesoscopic Individual-Vehicle Link Transmission Model_.
> Software, https://github.com/sjschlapbach/mesoLTM
> DOI: [10.5281/zenodo.21443220](https://doi.org/10.5281/zenodo.21443220)

As a **secondary reference**, please also cite the paper whose model `mesoltm`
implements, and whose `abmmeso` package (by Felipe de Souza, AGPL-3.0) it adapts
(see [`NOTICE`](NOTICE)):

> F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère,
> _"A mesoscopic link-transmission-model able to track individual vehicles"_,
> Simulation Modelling Practice and Theory **140** (2025) 103088.
> DOI: [10.1016/j.simpat.2025.103088](https://doi.org/10.1016/j.simpat.2025.103088)

Deviations from the paper's formulation are documented on the
[Deviations from the paper](docs/model/deviations-from-the-paper.md) page of the
documentation.

## License

`mesoltm` is distributed under the **GNU Affero General Public License v3.0 or
later** — see [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
