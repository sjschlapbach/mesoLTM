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

"""Discrete (individual-vehicle) Link Transmission Model link.

The demand/supply arithmetic, the T1/T2 wave-travel-time lags, and the integer
capacity-token accumulators are ported verbatim from the reference ``abmmeso``
implementation (``discrete/link.py``) so that results match the paper
(de Souza et al., SIMPAT 140 (2025) 103088). Do not change the arithmetic here.
"""

from __future__ import annotations

import math

from .base_link import BaseLink
from .vehicle import Vehicle


class Link(BaseLink):
    """A directed road link governed by the discrete LTM.

    The link is parameterised by a triangular fundamental diagram: free-flow
    speed ``v_f``, backward shock-wave speed ``w`` and jam density ``rho_jam``.
    Capacity is derived as ``rho_jam * v_f * w / (v_f + w)``. State is stored as
    cumulative inflow/outflow counts plus two integer capacity-token series that
    make the node flows integer-valued (one unit of flow == one vehicle).

    Paper notation (de Souza et al., SIMPAT 140 (2025) 103088), for cross-reading
    the equations cited in the methods below — code name -> paper symbol:
        ``cumulative_inflows`` -> F_a(i), ``cumulative_outflows`` -> G_a(i);
        ``cap_disc_downstream`` -> q̂^d_a(i) (discharge budget),
        ``cap_disc_upstream`` -> q̂^u_a(i) (entry budget);
        ``_demand`` -> D̂_a(i), ``_supply`` -> Ŝ_a(i);
        ``_inflow`` -> f̂_a(i), ``_outflow`` -> ĝ_a(i);
        ``capacity`` -> C_a, ``rho_jam`` -> K_a, ``length`` -> L_a,
        ``v_f`` -> V_a, ``w`` -> W_a, ``time_step`` -> Δt, step index ``t`` -> i.
    The discrete link model is Section 3.3 (Eqs. 6-7); the underlying continuous
    LTM identities and demand/supply are Section 3.1 (Eqs. 1-2).

    Attributes:
        link_id: Unique link identifier.
        length: Link length in metres.
        v_f: Free-flow speed (m/s).
        w: Backward shock-wave speed (m/s).
        rho_jam: Jam density (veh/m).
        capacity: Capacity (veh/s), derived in :meth:`start`.
        critical_occupancy: Largest whole-vehicle count that is still free-flowing
            (floored ``rho_crit * length``, ``rho_crit = rho_jam*w/(v_f+w)``),
            derived in :meth:`start`.
        jam_occupancy: Maximum whole-vehicle count that fits on the link (floored
            ``rho_jam * length``), derived in :meth:`start`.
        cumulative_inflows: Cumulative vehicles entered by step index.
        cumulative_outflows: Cumulative vehicles exited by step index.
        vehicles: FIFO queue of vehicles currently on the link.
    """

    def __init__(self, **kwargs: object) -> None:
        """Create a link.

        Args:
            **kwargs: Link parameters set directly on the instance. Typically
                ``link_id``, ``length``, ``v_f``, ``w``, ``rho_jam`` and optionally
                ``initial_capacity``. The keyword style mirrors the reference
                implementation so scenarios port over unchanged.
        """
        # Parameters and per-step state are declared with concrete types and
        # zero/empty defaults (the two-phase init pattern: real values arrive via
        # kwargs and start()). The transient flow scalars below are recomputed
        # every step before they are read.
        self.link_id: int = 0
        self.length: float = 0.0
        self.v_f: float = 0.0
        self.w: float = 0.0
        self.rho_jam: float = 0.0
        self.T1: int = 1
        self.T2: int = 1
        self.capacity: float = 0.0
        self.critical_occupancy: int = 0
        self.jam_occupancy: int = 0
        self.cumulative_inflows: list[float] = []
        self.cumulative_outflows: list[float] = []
        self.cap_disc_upstream: list[float] = []
        self.cap_disc_downstream: list[float] = []
        self.vehicles: list[Vehicle] = []
        self._inflow: int = 0
        self._outflow: int = 0
        self._demand: int = 0
        self._supply: int = 0
        self._cum_demand_term: float = 0.0
        # 0/1 look-ahead flag ("will this link have demand next step?"). Not used by
        # the flow arithmetic; it is a link-side hook consumed by a signalized
        # (traffic-light) node model — see get_next_step_demand.
        self._next_step_demand: int = 0
        self.initial_capacity: float | None = None

        for key, value in kwargs.items():
            setattr(self, key, value)

    def start(self, time_step: float, total_time: float) -> None:
        """Allocate cumulative-count and capacity-token arrays and derive lags.

        Args:
            time_step: Simulation step ``dt`` in seconds.
            total_time: Total simulated horizon in seconds.
        """
        total_steps = int(total_time / time_step)

        self.cumulative_inflows = [0 for _ in range(total_steps + 1)]
        self.cumulative_outflows = [0 for _ in range(total_steps + 1)]
        self.cap_disc_upstream = [0 for _ in range(total_steps + 1)]
        self.cap_disc_downstream = [0 for _ in range(total_steps + 1)]

        # CFL condition (paper Section 3.3): the fastest kinematic wave — the
        # free-flow speed v_f or the backward shock-wave speed w — must not cross
        # the whole link in less than one time step, i.e. max(v_f, w) * dt <= L.
        # Otherwise the discretisation is invalid and the T1/T2 lags would collapse
        # below one step. A tiny relative tolerance admits the exactly-one-step
        # boundary (e.g. auto-configured connector links).
        fastest_wave = max(self.v_f, self.w)
        if fastest_wave * time_step > self.length * (1.0 + 1e-9):
            raise ValueError(
                f"Link {self.link_id} violates the CFL condition (paper Section "
                f"3.3): max(v_f, w) * dt = {fastest_wave * time_step:.4g} m exceeds "
                f"the link length {self.length:.4g} m. Decrease the time step to "
                f"<= {self.length / fastest_wave:.4g} s or increase the link length "
                f"to >= {fastest_wave * time_step:.4g} m."
            )

        # T1/T2 (Eq. 2): T1 = floor(L / (V*dt)) forward (free-flow) wave lag,
        # T2 = floor(L / (W*dt)) backward (shock-wave) lag, both in whole steps.
        # Floored at 1 here since the CFL bound above guarantees each is >= 1.
        self.T1 = max(1, int(self.length / (self.v_f * time_step)))
        self.T2 = max(1, int(self.length / (self.w * time_step)))

        # Capacity C_a = K_a*V_a*W_a / (V_a+W_a) from the triangular FD (Section 3.1).
        self.capacity = self.rho_jam * self.v_f * self.w / (self.v_f + self.w)

        # Occupancy thresholds (whole vehicles) for auxiliary computations. On the
        # triangular FD the free-flow and congested branches meet at the critical
        # density rho_crit = K_a*W_a/(V_a+W_a) (where rho_crit*V_a == capacity); K_a
        # is the jam density (maximum packing). Occupancy is the vehicle count on the
        # link, so multiply each density by the length. Both are floored downward so
        # the integer count is conservative: a link holding at most critical_occupancy
        # vehicles has density <= rho_crit and is therefore still in free flow, and
        # jam_occupancy is the most vehicles that physically fit (matching the
        # rho_jam*length storage term used by the supply flow above).
        rho_crit = self.rho_jam * self.w / (self.v_f + self.w)
        self.critical_occupancy = math.floor(rho_crit * self.length)
        self.jam_occupancy = math.floor(self.rho_jam * self.length)
        # Seed the capacity tokens q̂^u/q̂^d at their upper bound ceil(C*dt)+1, the
        # cap imposed by Eq. (6); a link therefore starts able to discharge/admit a
        # full step's worth of capacity.
        if self.initial_capacity is not None:
            self.cap_disc_upstream[0] = self.initial_capacity
            self.cap_disc_downstream[0] = self.initial_capacity
        else:
            self.cap_disc_upstream[0] = math.ceil(self.capacity * time_step) + 1
            self.cap_disc_downstream[0] = math.ceil(self.capacity * time_step) + 1

    def set_inflow(self, vehicles: list[Vehicle], step: int) -> None:
        """Record vehicles entering the upstream end and append them to the queue.

        Args:
            vehicles: Vehicles crossing into this link this step.
            step: Current step index, supplied by the calling node for per-vehicle
                trajectory logging (it does not enter the flow arithmetic).
        """
        self._inflow = len(vehicles)
        self.vehicles.extend(vehicles)
        is_connector = getattr(self, "is_connector", False)
        for vehicle in vehicles:
            vehicle.record_entry(self.link_id, step, is_connector)

    def set_outflow(self, num_vehicles: int, step: int) -> list[Vehicle]:
        """Pop ``num_vehicles`` from the front of the queue (FIFO) and return them.

        Args:
            num_vehicles: Number of vehicles leaving the downstream end this step.
            step: Current step index, supplied by the calling node for per-vehicle
                trajectory logging (it does not enter the flow arithmetic).
        """
        self._outflow = num_vehicles
        popped = [self.vehicles.pop(0) for _ in range(num_vehicles)]
        for vehicle in popped:
            vehicle.record_exit(self.link_id, step)
        return popped

    def get_demand(self) -> int:
        """Return this step's sending flow (vehicles ready to leave)."""
        return self._demand

    def get_next_step_demand(self) -> int:
        """Return the 0/1 look-ahead demand flag for the next step.

        Not used by the core flow arithmetic; provided for signalized (traffic-
        light) node models, which read it to anticipate demand on an approach when
        deciding whether to hold or extend a green phase (as in the reference
        ``abmmeso`` ``signalizedNode``).
        """
        return self._next_step_demand

    def get_supply(self) -> int:
        """Return this step's receiving flow (vehicles the link can accept)."""
        return self._supply

    def get_capacity(self) -> float:
        """Return the link capacity in veh/s."""
        return self.capacity

    def get_cumulative_demand_term(self) -> float:
        """Return the un-capacitated sending-flow term used by node models."""
        return self._cum_demand_term

    def get_vehicle_from_index(self, index: int) -> Vehicle:
        """Peek the ``index``-th queued vehicle without removing it."""
        return self.vehicles[index]

    def update_state_variables(self, t: int, time_step: float) -> None:
        """Commit the step's flows into cumulative counts and refill capacity tokens.

        The two capacity-token series behave like token buckets: each step they
        replenish by ``capacity * dt`` and are debited by the actual flow, capped at
        ``ceil(capacity * dt) + 1``. This is what enforces an integer discharge/entry
        budget while tracking the continuous average capacity.

        Implements the cumulative-count identities of Eq. (1) and the capacity-token
        recursion of Eq. (6) (paper Section 3.1 and 3.3).

        Args:
            t: Current step index.
            time_step: Simulation step ``dt`` in seconds (passed in by the loop; the
                link no longer stores time state of its own).
        """
        # Eq. (1): F_a(i+1) = F_a(i) + f̂_a(i);  G_a(i+1) = G_a(i) + ĝ_a(i).
        self.cumulative_inflows[t + 1] = self.cumulative_inflows[t] + self._inflow
        self.cumulative_outflows[t + 1] = self.cumulative_outflows[t] + self._outflow

        # Eq. (6): q̂(i+1) = min{ q̂(i) + C*dt - flow(i), ceil(C*dt) + 1 }.
        # First term: unused capacity (C*dt minus the flow actually admitted/
        # discharged this step) carries over; second term caps the token bucket at
        # ceil(C*dt)+1 so it cannot accumulate unboundedly. Upstream token q̂^u is
        # debited by the inflow f̂; downstream token q̂^d by the outflow ĝ.
        self.cap_disc_upstream[t + 1] = min(
            self.cap_disc_upstream[t] - self._inflow + self.capacity * time_step,
            math.ceil(self.capacity * time_step) + 1,
        )
        self.cap_disc_downstream[t + 1] = min(
            self.cap_disc_downstream[t] - self._outflow + self.capacity * time_step,
            math.ceil(self.capacity * time_step) + 1,
        )

        # Clear transient flow scalars; they are recomputed before the next read.
        self._demand = 0
        self._supply = 0
        self._inflow = 0
        self._outflow = 0

    def get_flows_in_the_past_steps(self, t: int, steps: int) -> float:
        """Return the outflow over the last ``steps`` steps.

        Not used by the core flow arithmetic; provided for signalized (traffic-
        light) node models (as in the reference ``abmmeso`` ``signalizedNode``,
        e.g. for minimum-green / permitted-flow logic).
        """
        return self.cumulative_outflows[t] - self.cumulative_outflows[t - steps]

    def compute_demand_and_supplies(self, t: int) -> None:
        """Compute integer sending (demand) and receiving (supply) flows for step ``t``.

        Demand is the free-flow sending flow — vehicles that entered ``T1`` steps
        ago and have not yet left — capped by the downstream capacity token.
        Supply is the receiving flow — jam storage ``rho_jam * length`` freed by
        vehicles that left ``T2`` steps ago, minus those still present — capped by
        the upstream capacity token. Both first terms are floored to integers.

        This is the discrete link model, Eq. (7) of paper Section 3.3:
            D̂_a(i) = min{ floor(F_a(i-T1+1) - G_a(i)), floor(q̂^d_a(i)) }
            Ŝ_a(i) = min{ floor(G_a(i-T2+1) + K_a*L_a - F_a(i)), floor(q̂^u_a(i)) }
        i.e. the floored continuous demand/supply of Eq. (2) capped by the floored
        capacity token of Eq. (6). The first ``min`` term is free-flow/queue driven,
        the second is discretised-capacity driven.

        Args:
            t: Current step index (paper index ``i``).
        """
        # Warm-up: before T1-1 no vehicle has yet traversed the link at free flow
        # (the F(i-T1+1) lag term would index before the start), so demand is 0.
        if t < self.T1 - 1:
            self._demand = 0
            self._cum_demand_term = 0
            self._next_step_demand = 0
        else:
            # Eq. (7), first line. First term F(i-T1+1) - G(i): vehicles that
            # entered T1 steps ago (so their free-flow travel is complete) and have
            # not yet left. Second term: the downstream discharge token q̂^d.
            self._demand = min(
                math.floor(
                    self.cumulative_inflows[t - self.T1 + 1]
                    - self.cumulative_outflows[t]
                ),
                math.floor(self.cap_disc_downstream[t]),
            )
            # Un-floored first term (Eq. 2), used by the node models to break ties
            # between competing inbound links (fractional priority accounting).
            self._cum_demand_term = (
                self.cumulative_inflows[t - self.T1 + 1] - self.cumulative_outflows[t]
            )

            # Look-ahead 0/1 flag: does a vehicle arrive at the front next step, or
            # is demand already pending? Feeds signalized node models only; it does
            # not affect the demand/supply/flow arithmetic.
            queue_addition = (
                self.cumulative_inflows[t - self.T1 + 2]
                - self.cumulative_inflows[t - self.T1 + 1]
            )
            if queue_addition > 0 or self._cum_demand_term > 0:
                self._next_step_demand = 1
            else:
                self._next_step_demand = 0

        # Warm-up: before T2-1 the backward wave has not returned, so the link is
        # empty from the supply side — it can accept up to its entry token q̂^u.
        if t < self.T2 - 1:
            self._supply = int(self.cap_disc_upstream[t])
        else:
            # Eq. (7), second line. First term G(i-T2+1) + K*L - F(i): jam storage
            # K*L, plus room freed by vehicles that left T2 steps ago (the backward
            # shock-wave lag), minus vehicles currently on the link. Second term: the
            # upstream entry token q̂^u.
            self._supply = min(
                math.floor(
                    self.rho_jam * self.length
                    + self.cumulative_outflows[t - self.T2 + 1]
                    - self.cumulative_inflows[t]
                ),
                math.floor(self.cap_disc_upstream[t]),
            )
            self._supply = int(self._supply)

    def get_output_records(
        self, sample_time: float, sim_time_step: float, total_time: float
    ) -> list[dict]:
        """Return per-interval inflow/outflow records sampled at ``sample_time``.

        This is an output/aggregation helper, not part of the model dynamics. It
        turns the cumulative curves F_a (``cumulative_inflows``) and G_a
        (``cumulative_outflows``) of Eq. (1) into interval-averaged flow rates: the
        average flow over a window is the slope of the cumulative curve across it,
        ``[F(t2) - F(t1)] / (t2 - t1)`` (veh/s). ``sample_time`` may be coarser than
        the simulation step, so each output window spans several simulation steps.

        Args:
            sample_time: Output sampling interval in seconds (may be coarser than
                the simulation step).
            sim_time_step: Simulation step ``dt`` in seconds, passed in by the loop.
            total_time: Total simulated horizon in seconds, passed in by the loop.

        Returns:
            A list of dicts with keys ``time``, ``link_id``, ``inflow``,
            ``outflow``, ``cumulative_inflow`` and ``cumulative_outflow``.
        """
        total_steps = int(total_time / sample_time)
        records = []

        for t in range(total_steps + 1):
            # Map this output window [t, t+1)*sample_time onto simulation-step
            # indices into the cumulative arrays (which are indexed by sim step).
            start_step = int((t * sample_time) / sim_time_step)
            next_st = min(
                int(((t + 1) * sample_time) / sim_time_step),
                len(self.cumulative_inflows) - 1,
            )

            cumulative_inflow: float
            cumulative_outflow: float
            if t == 0:
                cumulative_inflow = 0
                cumulative_outflow = 0
            else:
                cumulative_inflow = self.cumulative_inflows[start_step]
                cumulative_outflow = self.cumulative_outflows[start_step]

            if t < total_steps:
                # Interval-averaged rate = slope of the cumulative curve over the
                # window: [F(next) - F(start)] / sample_time (and likewise for G).
                inflow = (
                    self.cumulative_inflows[next_st]
                    - self.cumulative_inflows[start_step]
                ) / sample_time
                outflow = (
                    self.cumulative_outflows[next_st]
                    - self.cumulative_outflows[start_step]
                ) / sample_time
            else:
                inflow = None
                outflow = None

            records.append(
                {
                    "time": t * sample_time,
                    "link_id": self.link_id,
                    "inflow": inflow,
                    "outflow": outflow,
                    "cumulative_inflow": cumulative_inflow,
                    "cumulative_outflow": cumulative_outflow,
                }
            )

        return records
