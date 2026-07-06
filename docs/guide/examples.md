# Examples

The repository ships runnable example scripts under
[`examples/`](https://github.com/sjschlapbach/mesoLTM/tree/master/examples). Run
any with `python examples/<name>.py`; each writes its figures (and any CSVs) to
`examples/output/<script_name>/`. This page is just an index — the concepts are
covered in the guide pages linked in the last column.

| Script | What it shows | Guide |
|--------|---------------|-------|
| `grid_demo.py` | A partial grid with shortest-path routing | [Routing](routing.md) |
| `freeway_onramp.py` | A freeway on-ramp merge on a calibrated topology with a synthetic demand profile | [Building networks](building-networks.md) |
| `parallel_links_demo.py` | Fast lane, slow lane, and a detour: free-flow vs congestion-aware routing | [Routing](routing.md) |
| `congestion_aware_routing.py` | A `ReroutingPlugin` balancing a burst across a short and long route by load | [Plugins](plugins.md) |
| `rerouting_demo.py` | Manual per-vehicle rerouting onto a detour mid-run | [Plugins](plugins.md) |
| `adaptive_rerouting_intersection.py` | An uncontrolled 2-in/2-out junction; agents re-checked against the live shortest path each step | [Plugins](plugins.md), [Routing](routing.md) |
| `bottleneck_access_policy.py` | A coin-toss bottleneck admission policy driven with `start`/`step`/`inject`, recorded as a video | [Stepping & injection](stepping-and-injection.md), [Animations](animations.md) |
| `vehicle_metrics_demo.py` | Per-vehicle travel times and travel-time plots | [Metrics](metrics.md), [Visualizations](visualizations.md) |
| `grid_visualization.py` | Congestion-aware grid rerouting recorded as a video, coloured by next link and by custom `props` | [Animations](animations.md) |
| `paper_validation.py` | Reproduces the paper's Section 4 figures through the shipped pipeline | [Deviations from the paper](../model/deviations-from-the-paper.md) |

!!! tip "Reproducing the paper"
    `paper_validation.py` is the canonical paper-reproduction script — it
    reproduces the paper's lane-drop, diverge, and merge figures and surfaces the
    deliberate divergences (discrete-only, CFL rejection, out-of-scope scenarios)
    on the figures themselves.
