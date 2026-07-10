# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""JSON scenario I/O: describe a whole simulation in a file and load/run it.

The schema is a superset of the network topology (see
:func:`~mesoltm.network.builders.network_to_dict`) plus timing, demand and output
settings, so a scenario can be shared and run from the command line without
writing Python.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..core.simulation import Simulation
from ..core.vehicle import Vehicle
from ..demand.demand import vehicles_from_demand_profile
from ..network.network import Network


def _parse_route(route_str: str) -> tuple[int, ...]:
    """Parse a ``"1,2,4"`` route string into a tuple of integer link ids."""
    return tuple(int(x) for x in route_str.replace("(", "").replace(")", "").split(","))


def build_scenario(data: dict, base_path: Path | None = None) -> Simulation:
    """Build a :class:`Simulation` from a parsed scenario dict.

    Args:
        data: The scenario dictionary (see module docstring for the schema).
        base_path: Directory used to resolve relative output file paths.

    Returns:
        A configured simulation ready to :meth:`run`.
    """
    net = Network(default_fd=data.get("default_fd"))

    for node in data.get("nodes", []):
        pos = tuple(node["pos"]) if node.get("pos") is not None else None
        net.add_node(node["id"], pos=pos)

    for link in data["links"]:
        fd = {k: link[k] for k in ("v_f", "w", "rho_jam") if k in link}
        net.add_link(
            link["u"],
            link["v"],
            length=link["length"],
            link_id=link.get("id"),
            **fd,
        )

    total_time = data["total_time"]
    for origin in data.get("origins", []):
        node = origin["node"]
        vehicles: list[Vehicle] = []
        demand = origin.get("demand")
        if demand is not None:
            profile = demand["profile"]
            horizon = demand.get("total_time", total_time)
            route = demand.get("route")
            shares = demand.get("route_shares")
            route_integer_share = None
            if shares is not None:
                route_integer_share = {_parse_route(k): v for k, v in shares.items()}
            vehicles = vehicles_from_demand_profile(
                profile,
                horizon,
                route=route,
                route_integer_share=route_integer_share,
                random_route=demand.get("random_route", False),
                origin=node,
                destination=demand.get("destination", 0),
            )
        net.set_origin(node, vehicles=vehicles)

    for node in data.get("destinations", []):
        net.set_destination(node)

    sim = net.compile(time_step=data["time_step"], total_time=total_time)

    base_path = base_path or Path(".")
    if data.get("link_output_file"):
        out = base_path / data["link_output_file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        sim.output_link_file = str(out)
        sim.link_output_sample_time = data.get("link_output_sample_time")
    if data.get("trip_output_file"):
        out = base_path / data["trip_output_file"]
        out.parent.mkdir(parents=True, exist_ok=True)
        sim.trip_output_file = str(out)
    return sim


def load_scenario(path: str | Path) -> Simulation:
    """Load a JSON scenario file and build its simulation.

    Args:
        path: Path to the ``.json`` scenario file.

    Returns:
        A configured :class:`Simulation`.
    """
    path = Path(path)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return build_scenario(data, base_path=path.parent)


def save_scenario(data: dict, path: str | Path) -> None:
    """Write a scenario dictionary to a JSON file.

    Args:
        data: The scenario dictionary.
        path: Destination path.
    """
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
