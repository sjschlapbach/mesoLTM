# Nodes & flow resolution

Links produce demand and supply; **nodes** decide how much actually moves. Each
node model is a small algorithm that reads the demand of its inbound links and the
supply of its outbound links and commits integer flows, moving vehicles front-of-
queue. The models are ported verbatim from the paper's Algorithms 1–3.

## The junction models

### One-to-one node

A single inbound link feeding a single outbound link. The flow is simply the
smaller of the inbound demand and the outbound supply (paper Eq. 11). This is the
node inserted along a corridor.

::: mesoltm.core.nodes.one_to_one_node.OneToOneNode
    options:
      show_root_heading: true
      members: false
      show_source: false

### Diverge node

One inbound link splitting to several outbound links. Vehicles are served **FIFO**:
the front vehicle's chosen outbound link is read (from its route, via the
[routing policy](../guide/routing.md)), and the whole stream is limited by the
first outbound link whose supply is exhausted — the paper's Algorithm 1. This
first-in-first-out coupling is what makes a blocked turn hold up the vehicles
behind it.

### Merge node

Several inbound links competing for one outbound link's scarce supply. Supply is
shared by **priority** (Algorithm 2). Priorities can be given two ways:

- an integer `priority_vector` (the reference form), or
- shares `alpha` — `alpha[i]` is the fraction of outbound supply inbound link `i`
  may claim, summing to 1.

```python
from mesoltm import MergeNode
# Two approaches, 75% / 25% split of the downstream supply.
node = MergeNode(node_id="m", outbound_link=out, inbound_links=[a, b],
                 alpha=[0.75, 0.25])
```

If **neither** is supplied, the node defaults to **capacity-proportional**
priorities (each inbound link weighted by its own capacity), resolved once
capacities are known. See [Deviations §B2](deviations-from-the-paper.md).

### General node model

The many-to-many junction: several inbound links, several outbound links,
arbitrary turning movements, with **outbound locking** so a saturated outbound
link correctly blocks all movements that need it (Algorithm 3). This is the model
the `Network` builder uses for real intersections, and it is what makes
uncontrolled junctions and reroutes behave sensibly.

## Origins and destinations

**Origin nodes** hold a vertical entry queue: vehicles wait (occupying no road
space) until their departure time and until the first link has supply, then are
released. On a general graph the origin feeds a [connector link](networks-and-connectors.md)
that holds the whole queue.

**Destination nodes** absorb arriving vehicles, stamping each vehicle's arrival
step. `node.get_arrived_trips()` returns the completed-trip records.

```python
# After a run:
arrived = sum(len(n.get_arrived_trips()) for n in sim.nodes)
```

## Priorities: shares ↔ integer vector

Internally the merge/general nodes consume an integer `priority_vector`; the
`alpha` shares you pass are converted to it by
[`priority_vector_from_alpha`](../reference/nodes.md#merge-priorities). When built
through the `Network`, override a node's shares after the fact:

```python
net.set_merge_priorities(node_id, {inbound_link_id: 0.7, other_link_id: 0.3})
```

For the full node API, see the [Nodes reference](../reference/nodes.md).
