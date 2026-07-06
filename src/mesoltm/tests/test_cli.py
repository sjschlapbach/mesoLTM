# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""End-to-end tests for the ``mesoltm`` command-line entry point.

These exercise the real ``mesoltm.cli.main`` path — the same code the installed
``mesoltm`` console script and ``python -m mesoltm`` invoke — so that running a
JSON scenario from the command line stays covered by the test suite.
"""

from __future__ import annotations

from ..cli import main
from ..io.scenario import save_scenario


def _write_scenario(directory) -> str:
    """Write a small, self-contained scenario (with CSV outputs) and return its path."""
    scenario = {
        "time_step": 1.0,
        "total_time": 120.0,
        "nodes": [{"id": "n1", "pos": [0, 0]}, {"id": "n2", "pos": [1, 0]}],
        "links": [
            {
                "id": 1,
                "u": "n1",
                "v": "n2",
                "length": 300,
                "v_f": 30.0,
                "w": 6.0,
                "rho_jam": 0.2,
            }
        ],
        "origins": [
            {
                "node": "n1",
                "demand": {
                    "profile": [0.5, 0.5],
                    "route_shares": {"1": 1},
                    "destination": "n2",
                },
            }
        ],
        "destinations": ["n2"],
        "link_output_file": "links.csv",
        "trip_output_file": "trips.csv",
    }
    path = directory / "scenario.json"
    save_scenario(scenario, path)
    return str(path)


def test_cli_runs_scenario_and_writes_outputs(tmp_path, capsys):
    """`main([scenario])` runs the sim, exits 0, and writes the configured CSVs."""
    scenario_path = _write_scenario(tmp_path)

    exit_code = main([scenario_path])

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "Simulation complete" in out
    # Output paths in the scenario are resolved relative to the scenario file.
    assert (tmp_path / "links.csv").exists()
    assert (tmp_path / "trips.csv").exists()


def test_cli_help_exits_cleanly(capsys):
    """`--help` prints usage and exits 0 (argparse raises SystemExit(0))."""
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    else:  # pragma: no cover - argparse always exits on --help
        raise AssertionError("--help should raise SystemExit")
    assert "usage: mesoltm" in capsys.readouterr().out
