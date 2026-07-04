"""Per-vehicle travel-time metrics: collect and visualise trip data.

Builds a small network where a single origin feeds two parallel A->B links — a
short main link and a longer detour — that merge and pass through a downstream
bottleneck. Vehicles are split 50/50 across the two routes, so both the route a
vehicle takes and the queueing it experiences make per-vehicle travel times
differ. After the run we collect one record per vehicle (overall travel time,
origin queue delay, and the travel time on each link it traversed), print a
compact summary, and draw visualisations from the collected data — including a
per-link time series that shows the downstream bottleneck's travel time climbing
over the run as a queue forms (congestion building up, link by link).

Every record is keyed by ``vehicle_id`` — the same identifier the routing layer
sees on each ``Vehicle`` — so the trip data stays associatable with the specific
vehicle (the basis for modelling heterogeneous drivers later).

Run: ``python examples/vehicle_metrics_demo.py``
"""

from __future__ import annotations

import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from _common import savefig  # noqa: E402

from mesoltm import Network, vehicles_from_demand_profile  # noqa: E402
from mesoltm.metrics import (  # noqa: E402
    collect_trips,
    summarize_trips,
    write_trips_csv,
)
from mesoltm.visualizations.plots import (  # noqa: E402
    plot_link_time_series,
    plot_link_travel_times,
    plot_network,
    plot_travel_time_distribution,
)

SUBDIR = pathlib.Path(__file__).stem  # figures go to output/<this script name>/

DT = 1.0
TOTAL_TIME = 500.0
LOAD_TIME = 150.0
MAIN_FD = {"v_f": 15.0, "w": 5.0, "rho_jam": 0.15}  # capacity ~0.56 veh/s
BOTTLENECK_RHO_JAM = 0.06  # lower jam density => capacity ~0.23 veh/s


def build() -> tuple[Network, dict]:
    """Assemble the network and return it with a map of named link ids."""
    net = Network(default_fd=MAIN_FD)  # every link uses MAIN_FD unless overridden
    for node, pos in {"O": (0, 0), "A": (1, 0), "B": (2, 0), "D": (3, 0)}.items():
        net.add_node(node, pos=pos)  # positions for the network plot
    l_in = net.add_link("O", "A", length=300.0)
    l_main = net.add_link("A", "B", length=300.0)
    l_detour = net.add_link("A", "B", length=600.0)  # longer parallel link
    l_out = net.add_link(
        "B", "D", length=300.0, rho_jam=BOTTLENECK_RHO_JAM
    )  # bottleneck

    # Half the vehicles take the main link, half the (longer) detour.
    vehicles = vehicles_from_demand_profile(
        [0.4] * 15,
        LOAD_TIME,
        route_integer_share={(l_in, l_main, l_out): 1, (l_in, l_detour, l_out): 1},
        origin="O",
        destination="D",
    )
    net.set_origin("O", vehicles=vehicles)
    net.set_destination("D")

    return net, {
        "in": l_in,
        "main": l_main,
        "detour": l_detour,
        "out": l_out,
    }


def main() -> None:
    """Run the scenario, collect metrics, print a summary, and save figures."""
    net, link_ids = build()
    sim = net.compile(time_step=DT, total_time=TOTAL_TIME).run()

    trips = collect_trips(sim)
    summary = summarize_trips(trips)

    print(f"Completed trips: {summary['n_completed']} / {summary['n_trips']}")
    print(
        f"Travel time (s): mean={summary['mean_travel_time']:.1f}  "
        f"median={summary['median_travel_time']:.1f}  "
        f"min={summary['min_travel_time']:.1f}  max={summary['max_travel_time']:.1f}"
    )
    print(f"Mean access time (queue + connector): {summary['mean_access_time']:.1f} s")
    print(f"Total vehicle-hours: {summary['total_vehicle_hours']:.2f}")
    print("Mean travel time per link:")

    name_by_id = {v: k for k, v in link_ids.items()}
    for lid, secs in summary["mean_link_travel_time"].items():
        print(f"  link {lid} ({name_by_id.get(lid, '?')}): {secs:.1f} s")

    # Per-vehicle data is keyed by vehicle_id: show two vehicles on different
    # routes to illustrate that the links traversed (and their times) differ.
    print("\nExample per-vehicle records (associatable by vehicle_id):")
    for record in (trips[0], trips[1]):
        links = ", ".join(
            f"{lid}:{secs:.0f}s" for lid, secs in record["link_travel_times"].items()
        )
        print(
            f"  vehicle {record['vehicle_id']}: total={record['travel_time']:.0f}s "
            f"(access={record['access_time']:.0f}s + "
            f"network={record['network_time']:.0f}s)  "
            f"route={record['route']}  links[{links}]"
        )

    csv_path = pathlib.Path(__file__).parent / "output" / SUBDIR
    csv_path.mkdir(parents=True, exist_ok=True)
    write_trips_csv(trips, str(csv_path / "trips.csv"))

    # Network coloured by total flow (the shared bottleneck and the two parallel
    # A->B links stand out), plus the travel-time distribution and per-link means.
    matplotlib.use("Agg")
    state = sim.network_state
    assert state is not None  # set by compile()
    fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))
    plot_network(state, color_by="flow", annotate_links=True, ax=axes[0])
    plot_travel_time_distribution(trips, ax=axes[1])
    plot_link_travel_times(trips, ax=axes[2])
    fig.tight_layout()
    path = savefig(fig, "vehicle_metrics", subdir=SUBDIR)

    # Second figure: one panel per link showing the travel time experienced on it
    # over the run (running average). The downstream bottleneck ("out") meters flow
    # at its capacity, so a queue forms *upstream* and spills back onto the feeder
    # links: "main"/"detour" crossing times climb over the run (congestion forming),
    # while "in" and the bottleneck link itself stay near free-flow.
    order = ["in", "main", "detour", "out"]
    fig2, ts_axes = plt.subplots(1, 4, figsize=(18, 3.8), sharey=True)
    plot_link_time_series(
        sim,
        [link_ids[name] for name in order],
        labels=order,
        window=4,
        axes=ts_axes,
    )
    fig2.suptitle("Per-link travel time over time (congestion build-up)")
    fig2.tight_layout()
    ts_path = savefig(fig2, "link_travel_time_series", subdir=SUBDIR)

    print(f"\nFigure saved to {path}")
    print(f"Time-series figure saved to {ts_path}")
    print(f"Trip CSV saved to {csv_path / 'trips.csv'}")


if __name__ == "__main__":
    main()
