# Nodes

Node models resolve how vehicles move across junctions each step, turning link
demand/supply into integer flows. `BaseNode` is the interface (and the routing
seam); the concrete models implement the paper's flow-resolution algorithms.
`OriginNode`/`DestinationNode` inject and absorb vehicles. See
[Nodes & flow resolution](../model/nodes.md) for the theory.

## Junction models

::: mesoltm.core.nodes.base_node.BaseNode

::: mesoltm.core.nodes.one_to_one_node.OneToOneNode

::: mesoltm.core.nodes.diverge_node.DivergeNode

::: mesoltm.core.nodes.merge_node.MergeNode

::: mesoltm.core.nodes.general_node_model.GeneralNodeModel

## Origins and destinations

::: mesoltm.core.nodes.origin_node.OriginNode

::: mesoltm.core.nodes.destination_node.DestinationNode

## Merge priorities

`MergeNode`/`GeneralNodeModel` accept priorities either as an integer
`priority_vector` (the reference form) or as shares `alpha`. This helper converts
shares to the equivalent integer vector the node arithmetic consumes.

::: mesoltm.core.priorities.priority_vector_from_alpha
