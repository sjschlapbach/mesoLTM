# Running a scenario

A **scenario** describes a whole simulation — topology, timing, demand, and
outputs — in a single JSON file, so it can be shared and run without writing
Python:

```bash
python -m mesoltm scenario.json
```

This builds the network, runs the simulation, prints how many vehicles arrived,
and writes any configured CSV outputs. Relative output paths are resolved against
the scenario file's directory.

## Example

```json
{
  "time_step": 1.0,
  "total_time": 600.0,
  "nodes": [
    {"id": "n1", "pos": [0, 0]},
    {"id": "n2", "pos": [1, 0]},
    {"id": "n3", "pos": [2, 0]},
    {"id": "n4", "pos": [3, 0]}
  ],
  "links": [
    {"id": 1, "u": "n1", "v": "n2", "length": 300, "v_f": 30.0, "w": 6.0, "rho_jam": 0.2},
    {"id": 2, "u": "n2", "v": "n3", "length": 600, "v_f": 30.0, "w": 6.0, "rho_jam": 0.2},
    {"id": 3, "u": "n2", "v": "n3", "length": 300, "v_f": 30.0, "w": 6.0, "rho_jam": 0.1},
    {"id": 4, "u": "n3", "v": "n4", "length": 300, "v_f": 30.0, "w": 6.0, "rho_jam": 0.1}
  ],
  "origins": [
    {
      "node": "n1",
      "demand": {
        "profile": [0.5, 0.8, 0.2],
        "route_shares": {"1,2,4": 1, "1,3,4": 2}
      }
    }
  ],
  "destinations": ["n4"],
  "link_output_file": "output/scenario_links.csv",
  "trip_output_file": "output/scenario_trips.csv"
}
```

Two links (`2` and `3`) share the same endpoints `n2 → n3`: that is a **parallel
link** (a slow and a fast lane). The `route_shares` map splits demand 1:2 across
the two paths through them.

## Schema

The scenario schema is a superset of the network topology plus timing, demand and
output settings.

### Top level

| Key | Type | Required | Meaning |
|-----|------|----------|---------|
| `time_step` | number | ✓ | Simulation step `dt` in seconds |
| `total_time` | number | ✓ | Simulated horizon in seconds |
| `nodes` | array | ✓ | Node definitions (see below) |
| `links` | array | ✓ | Link definitions (see below) |
| `origins` | array | – | Origin nodes with optional demand |
| `destinations` | array | – | Node ids that absorb vehicles |
| `default_fd` | object | – | Default fundamental diagram `{v_f, w, rho_jam}` for links that omit it |
| `link_output_file` | string | – | CSV path for per-link flow output |
| `link_output_sample_time` | number | – | Output sampling interval (s); defaults to `min(total_time, 60)` |
| `trip_output_file` | string | – | CSV path for per-vehicle trip output |

### `nodes[]`

| Key | Type | Meaning |
|-----|------|---------|
| `id` | any | Node identifier (string or number) |
| `pos` | `[x, y]` | Optional layout position (used for plots/animation) |

### `links[]`

| Key | Type | Meaning |
|-----|------|---------|
| `u`, `v` | node id | Directed link from `u` to `v` |
| `length` | number | Link length in metres |
| `id` | int | Optional explicit link id (else auto-assigned) |
| `v_f`, `w`, `rho_jam` | number | Fundamental-diagram parameters; fall back to `default_fd` |

### `origins[].demand`

An origin may carry a time-varying demand profile instead of an explicit vehicle
list:

| Key | Type | Meaning |
|-----|------|---------|
| `profile` | number[] | Demand rate per bin, in veh/s |
| `total_time` | number | Horizon the profile spans (defaults to the scenario `total_time`) |
| `route` | int[] | A single fixed route (list of link ids) for all generated vehicles |
| `route_shares` | object | Map of `"1,2,4" → integer weight` to split demand across several routes |
| `random_route` | bool | Assign routes randomly by weight rather than round-robin |
| `destination` | node id | Destination stamped on generated vehicles |

!!! tip "Build scenarios from Python"
    `mesoltm.io.scenario` also exposes `build_scenario(data)`,
    `load_scenario(path)`, and `save_scenario(data, path)` if you want to generate
    or transform scenarios programmatically. See the
    [Scenarios & CLI reference](../reference/io-cli.md).
