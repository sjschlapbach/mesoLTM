# mesoltm JSON scenarios and CLI

Describe a whole simulation in a JSON file and run it without Python.

## CLI

```bash
python -m mesoltm scenario.json      # runs the scenario, writes configured CSVs
```

Also available as the `mesoltm` console script: `mesoltm scenario.json`. Prints the
number of arrived vehicles and any output paths. Exit code 0 on success.

## Python API

```python
from mesoltm.io.scenario import build_scenario, load_scenario, save_scenario

sim = load_scenario("scenario.json")   # -> Simulation
sim.run()
# build_scenario(data: dict, base_path=None) -> Simulation
# save_scenario(data: dict, path) -> None
```

## Example scenario

```json
{
  "time_step": 1.0,
  "total_time": 600.0,
  "nodes": [
    {"id": "n1", "pos": [0, 0]},
    {"id": "n2", "pos": [1, 0]},
    {"id": "n3", "pos": [2, 0]}
  ],
  "links": [
    {"id": 1, "u": "n1", "v": "n2", "length": 300, "v_f": 30.0, "w": 6.0, "rho_jam": 0.2},
    {"id": 2, "u": "n2", "v": "n3", "length": 600, "v_f": 30.0, "w": 6.0, "rho_jam": 0.2}
  ],
  "origins": [
    {"node": "n1", "demand": {"profile": [0.5, 0.8, 0.2], "route": [1, 2]}}
  ],
  "destinations": ["n3"],
  "link_output_file": "output/links.csv",
  "trip_output_file": "output/trips.csv"
}
```

## Schema

Top level:

```
time_step                 number   (required) simulation step dt (s)
total_time                number   (required) horizon (s)
nodes                     array    (required) [{id, pos?}]
links                     array    (required) [{u, v, length, id?, v_f?, w?, rho_jam?}]
origins                   array    [{node, demand?}]
destinations              array    [node_id, ...]
default_fd                object   {v_f, w, rho_jam} fallback for links
link_output_file          string   CSV path for per-link flows
link_output_sample_time   number   output sampling interval (s); default min(total_time, 60)
trip_output_file          string   CSV path for per-vehicle trips
```

`nodes[]`: `id` (any), `pos` (`[x, y]`, optional; used for layout/auto length).

`links[]`: `u`, `v` (node ids), `length` (m), `id` (int, optional), `v_f`/`w`/
`rho_jam` (fall back to `default_fd`).

`origins[].demand`:

```
profile         number[]  demand rate per equal time-bin (veh/s)
total_time      number    horizon the profile spans (default: scenario total_time)
route           int[]     single fixed route (link ids) for all generated vehicles
route_shares    object    {"1,2,4": weight} split demand across routes by integer weight
random_route    bool      draw routes randomly by weight (else round-robin)
destination     node_id   destination stamped on generated vehicles
```

Relative output paths resolve against the scenario file's directory.
