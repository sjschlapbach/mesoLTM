# mesoltm API reference (condensed)

Signature cheat-sheet of every public symbol. Everything below is re-exported from
the top-level `mesoltm` package except the `mesoltm.visualizations` and
`mesoltm.io`/`mesoltm.cli` entries (noted). `__version__ == "0.1.0"`.

## Links (mesoltm.core)

```python
Link(**kwargs)                       # kwargs: link_id, length, v_f, w, rho_jam, initial_capacity
BaseLink                             # interface all links implement
ConnectorLink(link_id, time_step, vehicle_budget, **kwargs)   # auto O/D buffer (T1=T2=1)
```

Key `Link` methods (mostly engine-internal): `start(time_step, total_time)`,
`get_capacity() -> float`, `get_demand() -> int`, `get_supply() -> int`.

## Vehicle and Simulation (mesoltm.core)

```python
Vehicle(vehicle_id=0, origin=0, destination=0, start=0.0, route=None, props=None, **kwargs)
#   attrs: route(list[int]), position(int), props(dict), trajectory(list[dict]), end(int|None)
#          journeys(list[dict], single source of truth for completed trips), active(bool)
Vehicle.next_link(current_link_id) -> int | None
Vehicle.advance_to(link_id) -> None
Vehicle.snapshot_journey() -> dict       # freeze current trip into a journey record
Vehicle.reset_for_new_journey() -> None  # clear live state before re-injection

Simulation(**kwargs)                 # links, nodes, time_step, total_time, plugins, ...
Simulation.run(progress=False) -> Simulation   # progress=True shows a tqdm bar on stderr
Simulation.start() -> Simulation
Simulation.step() -> int
Simulation.current_step              # next step to run
Simulation.total_steps               # int(total_time/time_step)
Simulation.inject(node_id, vehicle, at_time=None, check_reentry_node=True) -> None
#   re-inject the same vehicle for another trip once it has arrived; one journey per trip
#   raises RuntimeError if still active; ValueError if re-entering at a different real node
Simulation.save_history(path=None) -> str
Simulation.network_state, .history, .nodes, .links
```

## Identifiers (mesoltm.core)

```python
NodeId  # = collections.abc.Hashable — a node id is any hashable value passed to
        #   Network.add_node (grid_network uses (row, col) tuples, corridor_network
        #   uses strings). Link ids are always plain int; recorded ids are int | str
        #   (int live, str after a JSON round-trip).
```

## Nodes (mesoltm.core.nodes)

```python
BaseNode()                                                  # interface; get_arrived_trips()
OneToOneNode(node_id, inbound_link, outbound_link)
DivergeNode(node_id, inbound_link, outbound_links)          # FIFO split (Algorithm 1)
MergeNode(node_id, outbound_link, inbound_links, priority_vector=None, alpha=None)
GeneralNodeModel(node_id, inbound_links, outbound_links, priority_vector=None, alpha=None)
OriginNode(node_id, link, demand_trips, **kwargs)           # add_trip(vehicle)
DestinationNode(node_id, link)                              # get_arrived_trips() -> list[dict]
# arrived-trip record keys: trip_id, origin, destination, start, end
```

Priority helper (not re-exported; `mesoltm.core.priorities`):

```python
priority_vector_from_alpha(alpha, resolution=12) -> list[int]
```

## Network (mesoltm.network)

```python
Network(default_fd=None)
Network.add_node(node_id, pos=None) -> node_id
Network.add_link(u, v, length=None, link_id=None, **fd) -> int
Network.set_origin(node_id, vehicles=None) -> None
Network.set_destination(node_id) -> None
Network.set_merge_priorities(node_id, alpha: dict) -> None
Network.compile(time_step, total_time, routing_policy=None, plugins=None,
                injection_budget=100, record_history=False, history_path=None,
                history_classify=None) -> Simulation

link_capacity(v_f, w, rho_jam) -> float

grid_network(rows, cols, link_length=200.0, spacing=1.0, fd=None, bidirectional=True,
             skip_nodes=None, skip_edges=None, all_nodes_od=False) -> Network
corridor_network(lengths, fd=None, node_prefix="n") -> Network
network_to_dict(net) -> dict         # {nodes, links, origins, destinations}
network_from_dict(data) -> Network
```

`NetworkState` (see [simulation.md](simulation.md) for the full method list):
`out_links/in_links/endpoints/length/capacity/free_flow_time/occupancy/density/
entry_queue/waiting_vehicles/vehicles_in_network/remaining_real_route/set_route/
inject/cumulative_inflow/cumulative_outflow`; attr `step`.

`VehicleView` = NamedTuple `(vehicle, link_id, route, destination)`.

## Routing (mesoltm.routing)

```python
RoutingPolicy                        # Protocol: next_link(vehicle, current_link_id, node, state) -> int|None
StaticRoutePolicy()                  # default; follows vehicle.route
ShortestPathPolicy(cost=None, dynamic=False)
#   .route(state, from_node, to_node) -> list[int]
#   .refresh(state) -> None
#   .next_link(vehicle, current_link_id, node, state) -> int | None
```

## Plugins (mesoltm.plugins)

```python
Plugin(state=None)                   # override run_step(t); start(time_step, total_time)
FunctionPlugin(fn, state=None)       # fn(t, state) -> None
ReroutingPlugin(reroute=None, state=None)
#   reroute(t, state, vehicles) -> dict[Vehicle, list[int]]   # vehicles: list[VehicleView]
```

## Demand (mesoltm.demand)

```python
vehicles_from_demand_profile(demand_pattern, total_time, route=None,
                             route_integer_share=None, random_route=False,
                             origin=0, destination=0) -> list[Vehicle]
```

## Metrics (mesoltm.metrics)

```python
collect_trips(sim, include_connectors=False) -> list[dict]   # one per journey; (vehicle_id, journey_index)
trip_record(journey, dt, include_connectors=False) -> dict   # journey record, not a live Vehicle
summarize_trips(trips) -> dict
write_trips_csv(trips, path) -> str
```

## Recording (mesoltm.recording; matplotlib-free)

```python
SimulationHistory                    # .save(path), .load(path), .from_state(state), frames
Frame                                # dataclass: step, time, agents, waiting, link_occupancy
AgentSnapshot                        # vehicle_id, link_id, queue_index, queue_len, route, next_link_id, next_node, category, props
WaitingSnapshot                      # vehicle_id, node_id, route, next_link_id, next_node, category, props
capture_frame(state, classify=None, step=None) -> Frame
record_run(sim, classify=None) -> SimulationHistory
```

## Visualizations (mesoltm.visualizations; needs [plot], NOT in top-level package)

```python
plot_cumulative_curves(sim, link_ids=None, ax=None)
plot_link_flow(sim, link_ids, window=60, window_seconds=None, ax=None)
plot_link_flows(sim, link_ids, labels=None, window=60, window_seconds=None, ax=None)
plot_link_time_series(sim, link_ids, labels=None, window=5, axes=None)
plot_network(state, color_by="occupancy", ax=None, node_size=260.0, annotate_links=False)
# submodule-only (mesoltm.visualizations.plots):
plot_travel_time_distribution(trips, ax=None, bins=20)
plot_link_travel_times(trips, ax=None)
# animation:
animate_simulation(sim, out_path, classify=None, **kwargs) -> str
animate_history(history, out_path, **kwargs) -> str
animate_from_history_file(history_path, out_path, **kwargs) -> str
save_animation(frames, layout, out_path, fps=25, subsample=1.0, dpi=150, palette=None, frames_dir=None, **render_kw) -> str
save_frames(frames, layout, out_dir, stride=1, dpi=150, prefix="frame_", palette=None, **render_kw) -> list[str]
render_frame(frame, layout, ax=None, palette=None, color_by="category", detail="auto", ...)
NetworkLayout                        # .from_state(state), .from_history(history)
resolve_palette(frames, palette=None, color_by="category") -> dict
expand_frame_indices(n_frames, subsample) -> list[int]
```

## Scenarios / CLI (mesoltm.io, mesoltm.cli)

```python
mesoltm.io.scenario.build_scenario(data, base_path=None) -> Simulation
mesoltm.io.scenario.load_scenario(path) -> Simulation
mesoltm.io.scenario.save_scenario(data, path) -> None
mesoltm.cli.main(argv=None) -> int   # `python -m mesoltm scenario.json`
```
