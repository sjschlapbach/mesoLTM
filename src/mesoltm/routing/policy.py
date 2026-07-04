# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Pluggable routing policies that decide a vehicle's next link at a node.

This is the single generalisation the mesoscopic model makes over the reference
``abmmeso`` implementation. There, a diverge/general node reads ``vehicle.route``
directly to find the next link. Here that one decision is delegated to a
``RoutingPolicy`` so external code (shortest path, agent auctions, dynamic access
rules) can override it without touching the flow arithmetic. The default policy
reproduces the reference behaviour exactly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from ..core.vehicle import Vehicle


@runtime_checkable
class RoutingPolicy(Protocol):
    """Interface for deciding the next link of a vehicle leaving a node."""

    def next_link(
        self,
        vehicle: Vehicle,
        current_link_id: int,
        node: object,
        state: object,
    ) -> int | None:
        """Return the ``link_id`` the vehicle should enter next.

        Args:
            vehicle: The vehicle being routed.
            current_link_id: The inbound link the vehicle is currently on.
            node: The node resolving the movement (gives access to candidate
                outbound links).
            state: A read-only network state view, or ``None``.

        Returns:
            The next ``link_id``, or ``None`` if no next link applies.
        """


class StaticRoutePolicy:
    """Default policy: follow each vehicle's own ``route`` (abmmeso-faithful).

    Resolution is delegated to :meth:`Vehicle.next_link`, which uses the vehicle's
    position pointer (robust to routes that revisit a link) and falls back to the
    first occurrence of the current link — matching the reference implementation.
    """

    def next_link(
        self,
        vehicle: Vehicle,
        current_link_id: int,
        node: object,
        state: object,
    ) -> int | None:
        """Return the vehicle's own-route next link (see :class:`RoutingPolicy`)."""
        # The route is fixed on the vehicle, so ``node`` and ``state`` are unused
        # here (a live router such as ShortestPathPolicy consults them instead).
        return vehicle.next_link(current_link_id)
