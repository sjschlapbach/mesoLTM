# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Command-line entry point: run a JSON scenario and write its CSV outputs."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .io.scenario import load_scenario


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ``mesoltm`` CLI.

    Parses a scenario path, runs the simulation, and writes any configured
    link/trip CSV outputs.

    Args:
        argv: Optional argument list (defaults to ``sys.argv``).

    Returns:
        Process exit code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        prog="mesoltm",
        description="Run a mesoscopic LTM traffic scenario from a JSON file.",
    )
    parser.add_argument("scenario", help="Path to the JSON scenario file")
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the progress bar shown while the simulation runs.",
    )
    args = parser.parse_args(argv)

    sim = load_scenario(args.scenario)
    sim.run(progress=not args.no_progress)

    arrived = sum(len(node.get_arrived_trips()) for node in sim.nodes)
    print(f"Simulation complete: {arrived} vehicles reached their destination.")
    if sim.output_link_file:
        print(f"Link output written to {sim.output_link_file}")
    if sim.trip_output_file:
        print(f"Trip output written to {sim.trip_output_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
