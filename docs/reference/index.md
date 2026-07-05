# API Reference

This section is generated automatically from the source docstrings with
[mkdocstrings](https://mkdocstrings.github.io/). It is a **reference**, not a
tutorial — for narrative explanations of how the pieces fit together, start with
[The Model](../model/overview.md) and the [User Guide](../guide/building-networks.md).

Everything listed here (except the plotting/animation helpers) is re-exported from
the top-level package, so the canonical way to import it is:

```python
import mesoltm as m
from mesoltm import Network, Vehicle, ShortestPathPolicy, ReroutingPlugin
```

The plotting and animation helpers live under `mesoltm.visualizations` and require
the optional `[plot]` extra — see [Visualizations](visualizations.md).

## Pages

| Page | Contents |
|------|----------|
| [Core](core.md) | Links, the `Vehicle` agent, and the `Simulation` loop |
| [Nodes](nodes.md) | Junction flow-resolution models + origins/destinations |
| [Network](network.md) | The `Network` builder, `NetworkState`, and grid/corridor builders |
| [Routing](routing.md) | Routing policies (`RoutingPolicy`, shortest path) |
| [Plugins](plugins.md) | Per-step loop hooks (`Plugin`, `ReroutingPlugin`) |
| [Metrics](metrics.md) | Per-vehicle trip records and summaries |
| [Demand](demand.md) | Demand-profile generation |
| [Recording](recording.md) | Animation history capture (matplotlib-free) |
| [Visualizations](visualizations.md) | Plots and movement animations (`[plot]` extra) |
| [Scenarios & CLI](io-cli.md) | JSON scenario I/O and the command line |
