# The simulation loop

The engine advances the network in discrete steps of `dt` seconds. Each step runs
a **fixed four-phase ordering**, ported verbatim from the reference runner. The
ordering is not incidental — demand/supply must be read before flows and committed
after.

## The four phases

For each step `t`:

1. **Plugins act.** Registered [plugins](../guide/plugins.md) run first, reading
   the [`NetworkState`](../reference/network.md#network-state) and changing the
   simulation before flows are computed — e.g. rerouting vehicles or gating links.
2. **Nodes prepare.** Origins release departing vehicles into their buffers.
3. **Links compute demand & supply.** Each link evaluates its integer sending
   flow $\hat{D}$ and receiving flow $\hat{S}$ for this step (see
   [Links & the FD](links-and-fd.md)).
4. **Nodes compute flows.** The node models turn demand/supply into integer flows
   and move vehicles front-of-queue across junctions (Algorithms 1–3).
5. **Links commit.** Each link folds the step's flows into its cumulative curves
   $F$/$G$ and refills its capacity tokens.

Phases 3 and 5 straddle the node phase so that demand/supply are current when the
nodes read them and committed once the nodes have acted.

## Two ways to drive it

### Batch: `run()`

```python
sim = net.compile(time_step=1.0, total_time=600.0)
sim.run()          # start() + step() to the horizon + write_outputs()
```

`run()` is the batch entry point and is kept behaviourally identical to the
reference.

### Step-driven: `start()` / `step()`

Drive the loop yourself to observe state and inject demand between steps — useful
for external controllers, admission policies, or dispatchers:

```python
sim = net.compile(time_step=1.0, total_time=600.0)
sim.start()
while sim.current_step < sim.total_steps:
    t = sim.step()
    # inspect sim.network_state here, and/or inject new demand:
    # sim.inject(node_id, Vehicle(...), at_time=None)  # defaults to now
```

`current_step` is the next step to run; `total_steps` is `total_time / dt`
floored. `run()` is literally `start()` + a loop of `step()` + output writing, so
the two styles are interchangeable and produce identical results.

## Dynamic injection

Between steps, `sim.inject(node_id, vehicle)` adds a vehicle to an origin's demand
mid-run. You supply a route over **real** link ids; the origin/destination
[connector links](networks-and-connectors.md) are spliced on automatically, and
the vehicle is inserted in departure-time order. This is a pure addition to a
node's demand list — it never perturbs the per-step arithmetic. See
[Deviations §B5](deviations-from-the-paper.md) and the
[Stepping & injection guide](../guide/stepping-and-injection.md).
