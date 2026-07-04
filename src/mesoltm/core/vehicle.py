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

"""Individual vehicle (trip) agent tracked through the mesoscopic LTM."""

from __future__ import annotations

from collections.abc import Sequence


class Vehicle:
    """A single vehicle with an explicit route through the network.

    In the mesoscopic model every unit of node flow corresponds to exactly one
    ``Vehicle``, so vehicles are tracked individually as they move front-of-queue
    from link to link. This is the discrete counterpart of the ``Trip`` object in
    the reference ``abmmeso`` implementation.

    Attributes:
        vehicle_id: Unique identifier of the vehicle.
        origin: Origin node/link identifier (bookkeeping only).
        destination: Destination node/link identifier (bookkeeping only).
        start: Departure time in seconds.
        route: Ordered sequence of ``link_id`` values the vehicle intends to
            traverse. The route may be mutated at any time (e.g. by a plugin or
            routing policy) to reroute the vehicle at its next node — the network
            only propagates the vehicle along whatever route it currently holds.
        position: Index of the vehicle's current link within ``route``. Used by
            the routing layer to resolve the next link robustly even when a route
            revisits a link (as can happen on grids).
        end: Arrival time step, set by the destination node when the vehicle
            exits the network (``None`` while still travelling).
        trajectory: Ordered per-link travel log, one entry per link the vehicle
            enters: ``{"link_id", "entry_step", "exit_step", "is_connector"}``.
            ``exit_step`` is ``None`` while the vehicle is still on that link.
            Populated automatically as the vehicle moves; the per-link and overall
            travel times are derived from it (see :mod:`mesoltm.metrics`).
    """

    def __init__(
        self,
        vehicle_id: int = 0,
        origin: object = 0,
        destination: object = 0,
        start: float = 0.0,
        route: Sequence[int] | None = None,
        **kwargs: object,
    ) -> None:
        """Create a vehicle.

        Args:
            vehicle_id: Unique identifier.
            origin: Origin identifier (bookkeeping).
            destination: Destination identifier (bookkeeping).
            start: Departure time in seconds.
            route: Ordered ``link_id`` sequence; copied into a mutable list.
            **kwargs: Extra attributes set directly on the instance (kept for
                compatibility with the reference implementation's keyword style).
        """
        self.vehicle_id = vehicle_id
        self.origin = origin
        self.destination = destination
        self.start = start
        self.route: list[int] = list(route) if route is not None else []
        self.position = 0
        self.end: int | None = None
        self.trajectory: list[dict] = []
        # Destination node cached by the network compiler for connector splicing.
        self._dest_node: object = None

        for key, value in kwargs.items():
            setattr(self, key, value)

    def record_entry(self, link_id: int, step: int, is_connector: bool = False) -> None:
        """Log that the vehicle entered ``link_id`` at simulation step ``step``.

        Opens a new trajectory segment whose ``exit_step`` is filled in later by
        :meth:`record_exit`. Called automatically by the link when the vehicle is
        placed onto it.

        Args:
            link_id: The link just entered.
            step: The simulation step index of entry.
            is_connector: Whether the link is an auto-inserted O/D connector (these
                are excluded from real per-link travel times by default).
        """
        self.trajectory.append(
            {
                "link_id": link_id,
                "entry_step": step,
                "exit_step": None,
                "is_connector": is_connector,
            }
        )

    def record_exit(self, link_id: int, step: int) -> None:
        """Log that the vehicle left ``link_id`` at simulation step ``step``.

        Closes the most recent still-open segment **for that link**. Matching on
        ``link_id`` (rather than assuming the last segment) is required because some
        node models place a vehicle on its next link before discharging it from the
        current one, so the open segments are not always in exit order.

        Args:
            link_id: The link just left.
            step: The simulation step index of exit.
        """
        for segment in reversed(self.trajectory):
            if segment["link_id"] == link_id and segment["exit_step"] is None:
                segment["exit_step"] = step
                return

    def next_link(self, current_link_id: int) -> int | None:
        """Return the link the vehicle should enter after ``current_link_id``.

        Resolution uses ``position`` when it is consistent with the current link
        (the common case, and robust to routes that revisit a link); otherwise it
        falls back to the first occurrence of ``current_link_id`` in ``route`` —
        matching the reference implementation's behaviour.

        Args:
            current_link_id: The link the vehicle is currently on.

        Returns:
            The next ``link_id`` in the route, or ``None`` if the current link is
            the last one in the route.
        """
        route = self.route
        if 0 <= self.position < len(route) and route[self.position] == current_link_id:
            idx = self.position
        else:
            try:
                idx = route.index(current_link_id)
            except ValueError:
                return None
            self.position = idx
        if idx + 1 < len(route):
            return route[idx + 1]
        return None

    def advance_to(self, link_id: int) -> None:
        """Advance the vehicle's position pointer onto ``link_id``.

        Called when the vehicle actually moves onto its next link so that the
        ``position`` index stays in sync with the vehicle's location.

        Args:
            link_id: The link the vehicle has just entered.
        """
        self.position += 1
        if not (
            0 <= self.position < len(self.route)
            and self.route[self.position] == link_id
        ):
            # Route was rewritten out from under us; resynchronise on the id.
            try:
                self.position = self.route.index(link_id)
            except ValueError:
                pass

    def __repr__(self) -> str:
        return (
            f"Vehicle(id={self.vehicle_id}, start={self.start}, "
            f"route={self.route}, position={self.position})"
        )
