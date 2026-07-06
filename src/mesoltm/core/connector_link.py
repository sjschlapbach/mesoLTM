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

"""Auto-configured connector link used to attach origins/destinations to junctions.

A connector is an ordinary discrete LTM :class:`~mesoltm.core.link.Link`; only its
parameters are chosen automatically so the user never has to configure it. It is a
one-cell, free-flow link (``T1 == T2 == 1``) sized to be a **transparent buffer**:
it never constrains flow itself, so the adjacent origin/junction/destination governs
the dynamics.

Design goal — minimum impact on the model. A source connector holds the whole
entry queue for its origin: it is given enough storage that the origin can always
release every waiting vehicle onto it (no vehicle ever queues at the origin *and*
on the connector at the same time), and enough per-step capacity that its discharge
is never the binding constraint (the downstream junction's supply and merge
priorities decide how many vehicles proceed, exactly as for any 1-lane link). A
vehicle entering an empty connector crosses it in a single free-flow step, so it
can enter the network immediately when the node serves it; vehicles that must wait
do so on the connector and are already part of its demand, so they are not further
delayed by a separate origin-to-connector hop.

True zero-length connectors are impossible in the LTM because storage capacity is
``rho_jam * length`` — a zero-length link could never store or admit a vehicle. A
one-cell buffer is the faithful approximation; see
docs/model/deviations-from-the-paper.md (B1).
"""

from __future__ import annotations

from .link import Link


class ConnectorLink(Link):
    """A one-cell, free-flow LTM link inserted automatically at origins/destinations.

    The fundamental-diagram parameters are derived from the time step and a
    ``vehicle_budget`` (the number of vehicles that could ever pass through the
    connector) so that neither its storage nor its per-step capacity is ever the
    binding constraint. See the module docstring for the rationale.
    """

    def __init__(
        self,
        link_id: int,
        time_step: float,
        vehicle_budget: int,
        **kwargs: object,
    ) -> None:
        """Create an auto-configured connector link.

        Args:
            link_id: Unique link identifier.
            time_step: Simulation step ``dt`` in seconds (sets the one-cell length
                and the free-flow speed so ``T1 == T2 == 1``).
            vehicle_budget: An upper bound on the number of vehicles that can ever
                traverse this connector (e.g. the scenario's total vehicle count).
                Storage and capacity are sized from it so the connector never backs
                up onto the origin and never caps its own discharge.
            **kwargs: Additional attributes forwarded to :class:`Link`.
        """
        # length 1 with v_f = w = 1/dt makes both the free-flow lag T1 and the
        # backward-wave lag T2 exactly one step, so a vehicle crosses an empty
        # connector without delay and freed space propagates back immediately.
        length = 1.0
        v_f = 1.0 / time_step
        w = v_f

        # Size the FD from the vehicle budget N (>= 1 to avoid a degenerate link).
        # With this triangular FD, capacity = rho_jam / (2*dt), so choosing
        # rho_jam = 2*N gives, simultaneously:
        #   * storage  = rho_jam * length = 2*N vehicles  (> any possible queue N,
        #     so the origin can always offload every waiting vehicle -> no double
        #     queueing), and
        #   * capacity * dt = N vehicles per step  (>= any per-step flow, so the
        #     connector's own discharge/entry token never binds and the junction /
        #     downstream supply is what governs).
        # The budget carries no dt term, so the buffer never shrinks for a larger
        # time step (unlike a fixed vehicle count would).
        budget = max(1, int(vehicle_budget))
        rho_jam = 2.0 * budget

        params: dict[str, object] = dict(
            link_id=link_id,
            length=length,
            v_f=v_f,
            w=w,
            rho_jam=rho_jam,
        )
        params.update(kwargs)
        super().__init__(**params)
        self.is_connector = True
