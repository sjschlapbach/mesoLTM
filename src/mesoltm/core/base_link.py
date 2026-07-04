# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.
#
# The traffic-flow logic in this module is adapted from the abmmeso package by
# Felipe de Souza (AGPL-3.0) and follows the model of:
#   F. de Souza, O. Verbas, J. Auld, C. M. J. Tampère, "A mesoscopic
#   link-transmission-model able to track individual vehicles", Simulation
#   Modelling Practice and Theory 140 (2025) 103088.
#   https://doi.org/10.1016/j.simpat.2025.103088

"""Abstract link interface shared by all link implementations."""

from __future__ import annotations

from .vehicle import Vehicle


class BaseLink:
    """Interface that every link type must provide to the node models and loop.

    A link owns a first-in-first-out queue of vehicles and, at every time step,
    reports a sending flow (``demand``) and a receiving flow (``supply``) that the
    node models use to decide how many vehicles may cross each boundary. Concrete
    subclasses implement the actual LTM dynamics.
    """

    link_id: int
    length: float

    def start(self, time_step: float, total_time: float) -> None:
        """Allocate per-step state for a simulation of ``total_time`` seconds."""

    def set_inflow(self, vehicles: list[Vehicle], step: int) -> None:
        """Append ``vehicles`` entering the link this step to its queue.

        ``step`` is the current step index (supplied by the calling node) used only
        for per-vehicle trajectory logging, not for the flow arithmetic.
        """

    def set_outflow(self, num_vehicles: int, step: int) -> list[Vehicle]:
        """Remove and return the first ``num_vehicles`` vehicles leaving the link.

        ``step`` is the current step index (supplied by the calling node) used only
        for per-vehicle trajectory logging, not for the flow arithmetic.
        """
        return []

    def get_capacity(self) -> float:
        """Return the link capacity in vehicles per second."""
        return 0.0

    def get_demand(self) -> int:
        """Return the number of vehicles ready to leave the downstream end."""
        return 0

    def get_next_step_demand(self) -> int:
        """Return a 0/1 look-ahead demand flag for the next step (signal models)."""
        return 0

    def get_supply(self) -> int:
        """Return the number of vehicles the upstream end can accept this step."""
        return 0

    def get_cumulative_demand_term(self) -> float:
        """Return the un-capacitated sending-flow term (used by node models)."""
        return 0.0

    def get_vehicle_from_index(self, index: int) -> Vehicle:
        """Peek the ``index``-th queued vehicle without removing it."""
        raise NotImplementedError

    def update_state_variables(self, t: int, time_step: float) -> None:
        """Commit this step's flows into the cumulative counts and state vars."""

    def compute_demand_and_supplies(self, t: int) -> None:
        """Compute this step's sending (demand) and receiving (supply) flows."""

    def get_output_records(
        self, sample_time: float, sim_time_step: float, total_time: float
    ) -> list[dict]:
        """Return per-interval flow records for CSV/analysis output."""
        return []
