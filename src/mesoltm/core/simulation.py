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

"""The simulation engine: the four-phase mesoscopic LTM time loop."""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING

from ..recording import SimulationHistory, capture_frame

if TYPE_CHECKING:
    from ..network.state import NetworkState
    from ..recording import ClassifyFn
    from .vehicle import Vehicle


class Simulation:
    """Runs the mesoscopic LTM over a set of links and nodes.

    The per-step ordering is ported verbatim from ``abmmeso``
    (``simulationengine/simulationRunner.py``): (1) plugins run first,
    (2) nodes prepare, (3) links compute demand/supply, (4) nodes move vehicles,
    (5) links commit their state. The plugin phase (``plugins``, the generalised
    ``general_purpose_objects`` slot) is the hook where external code can read
    state and change the simulation (e.g. reroute vehicles) before flows are
    computed.

    Two ways to drive the loop:

    * :meth:`run` — initialise, run the whole horizon, write outputs. This is the
      batch entry point and is kept byte-for-byte identical to the reference.
    * :meth:`start` + :meth:`step` — advance the simulation one step at a time so
      external code can observe state and :meth:`inject` new vehicles between
      steps (e.g. an external controller releasing vehicles on demand and
      re-injecting them at their current node into the next step's demand).

    Attributes:
        links: All links in the network.
        nodes: All nodes in the network.
        time_step: Simulation step ``dt`` in seconds.
        total_time: Simulated horizon in seconds.
        plugins: Optional objects with ``start`` / ``run_step`` run each step.
        current_step: Index of the next step to execute (``0`` before the first).
        network_state: Read-only state view attached by ``Network.compile``.
    """

    def __init__(self, **kwargs: object) -> None:
        """Create a simulation.

        Args:
            **kwargs: Typically ``links``, ``nodes``, ``time_step``,
                ``total_time`` and optionally ``plugins``,
                ``output_link_file``, ``trip_output_file``,
                ``link_output_sample_time``. Keyword style mirrors the reference
                implementation.
        """
        self.links: list = []
        self.nodes: list = []
        self.time_step: float = 0.0
        self.total_time: float = 0.0
        self.output_link_file: str | None = None
        self.trip_output_file: str | None = None
        self.link_output_sample_time: float | None = None
        self.plugins: list | None = None
        # Optional read-only state view attached by Network.compile.
        self.network_state: NetworkState | None = None
        # Stepping state (see start()/step()); ``current_step`` is the next step
        # to run and also the step new injections default into.
        self.current_step: int = 0
        self._started: bool = False
        # Per-step history logging for animation/video (off by default: it costs
        # memory and, if ``history_path`` is set, disk). When enabled, a frame is
        # captured after every step into ``history``; ``history_classify`` maps a
        # vehicle to a colour category. See mesoltm.recording.
        self.record_history: bool = False
        self.history_path: str | None = None
        self.history_classify: ClassifyFn | None = None
        self.history: SimulationHistory | None = None

        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def total_steps(self) -> int:
        """Number of discrete steps in the horizon (``total_time / dt``, floored)."""
        return int(self.total_time / self.time_step)

    def start(self) -> Simulation:
        """Initialise all links, nodes and plugins for the horizon.

        Idempotent: calling it again (or via :meth:`run`) after the first time is
        a no-op, so ``start()`` then ``step()`` and a bare ``run()`` are safe to
        mix. Must be called before :meth:`step`.

        Returns:
            ``self``.
        """
        if self._started:
            return self

        for link in self.links:
            link.start(self.time_step, self.total_time)
        for node in self.nodes:
            node.start(self.time_step, self.total_time)
        if self.plugins is not None:
            for obj in self.plugins:
                obj.start(self.time_step, self.total_time)

        self.current_step = 0

        # The simulation loop owns the state clock;
        # start it at 0 so state inspected before the first step reads correctly.
        if self.network_state is not None:
            self.network_state.step = 0

        # When history logging is on, open the history with the network geometry
        # and capture the initial (empty) frame, so frame 0 is the start state.
        if self.record_history and self.network_state is not None:
            self.history = SimulationHistory.from_state(self.network_state)
            self.history.frames.append(
                capture_frame(self.network_state, self.history_classify)
            )

        self._started = True
        return self

    def step(self) -> int:
        """Advance the simulation by exactly one step and return that step index.

        Runs the four LTM phases for ``current_step`` and increments it. Raises if
        the simulation has not been :meth:`start`-ed or the horizon is exhausted.
        Between steps, external code may read :attr:`network_state` and call
        :meth:`inject` to add vehicles to the upcoming step's demand.

        Returns:
            The index of the step that was just executed.
        """
        if not self._started:
            raise RuntimeError("call start() before step()")
        if self.current_step >= self.total_steps:
            raise RuntimeError(
                f"simulation exhausted: {self.total_steps} steps already run"
            )

        t = self.current_step
        self._run_step(t)
        self.current_step = t + 1
        return t

    def _run_step(self, t: int) -> None:
        """Execute the four-phase LTM ordering for a single step ``t``.

        Realises the discrete LTM of the paper (de Souza et al., SIMPAT 140
        (2025) 103088, Sections 3.3-3.4):
          1. plugins act first (external routing/gating hook);
          2. nodes prepare (origins release departing vehicles to their buffers);
          3. links compute discrete demand D̂ / supply Ŝ (Eq. 7);
          4. node models turn D̂/Ŝ into integer flows (Eq. 11, Algorithms 1-3);
          5. links commit those flows into F/G and refill capacity tokens
             (Eqs. 1 and 6). Phases 3 and 5 must straddle the node phase so
             demand/supply are read before flows and committed after.
        """
        # plugins and node models read ``state.step`` during the step,
        # so set it to t before they run.
        if self.network_state is not None:
            self.network_state.step = t

        if self.plugins is not None:
            for obj in self.plugins:
                obj.run_step(t)

        for node in self.nodes:
            node.prepare_step(t)

        for link in self.links:
            link.compute_demand_and_supplies(t)

        for node in self.nodes:
            node.compute_flows(t)

        for link in self.links:
            link.update_state_variables(t, self.time_step)

        # Flows for step t are now committed into cumulative index t+1; advance the
        # clock so code injecting/inspecting *between* steps sees the fresh state.
        if self.network_state is not None:
            self.network_state.step = t + 1

        # Capture the post-step state (state.step is now t+1) for the animation.
        if self.history is not None and self.network_state is not None:
            self.history.frames.append(
                capture_frame(self.network_state, self.history_classify)
            )

    def run(self) -> Simulation:
        """Initialise all objects, run the time loop, and write any outputs.

        Equivalent to :meth:`start` followed by :meth:`step` until the horizon is
        exhausted, then :meth:`write_outputs`. Kept behaviourally identical to the
        reference batch runner.

        Returns:
            ``self``, so callers can inspect link/node state after the run.
        """
        self.start()
        while self.current_step < self.total_steps:
            self.step()

        self.write_outputs()
        return self

    def inject(
        self, node_id: object, vehicle: Vehicle, at_time: float | None = None
    ) -> None:
        """Inject a vehicle into the network to depart from ``node_id``.

        The vehicle's ``route`` must be a sequence of real link ids reachable from
        ``node_id``; connector links (origin/destination access) are spliced on
        automatically, exactly as for static demand. Injected vehicles enter the
        origin's departure queue and are released once their departure time is
        reached and the first link has supply.

        Compile with ``injection_budget`` set to at least the number of vehicles you
        intend to inject: the origin/destination connectors are sized for it. If more
        vehicles are injected than that budget, a :class:`RuntimeWarning` is emitted
        because the connector buffer may be too small — the affected vehicle then
        waits in the origin queue (possibly not entering within the horizon) instead
        of being silently discarded.

        Args:
            node_id: An origin node (must have been marked via
                ``Network.set_origin``) to release the vehicle from.
            vehicle: The vehicle to inject; its ``start`` is overwritten with the
                effective departure time.
            at_time: Departure time in seconds. Defaults to the current step's time
                (``current_step * dt``), so the vehicle is considered for release
                in the very next :meth:`step`.

        Raises:
            RuntimeError: If no compiled network state is attached.
        """
        if self.network_state is None:
            raise RuntimeError(
                "inject() requires a network built via Network.compile()"
            )

        if at_time is None:
            at_time = self.current_step * self.time_step

        self.network_state.inject(node_id, vehicle, at_time=at_time)

    def get_times(self, added_step: int = 0) -> list[float]:
        """Return the sequence of simulated times in seconds.

        Args:
            added_step: Extra steps to append (e.g. ``1`` to include the final
                boundary matching the cumulative-count arrays).

        Returns:
            A list of times ``[0, dt, 2*dt, ...]``.
        """
        return [
            i * self.time_step
            for i in range(int(self.total_time / self.time_step) + added_step)
        ]

    def save_history(self, path: str | None = None) -> str:
        """Write the recorded history to ``path`` (defaults to ``history_path``).

        Args:
            path: Destination JSON file; falls back to ``self.history_path``.

        Returns:
            The path written to.

        Raises:
            RuntimeError: If nothing was recorded (``record_history`` was off) or
                no path is available.
        """
        if self.history is None:
            raise RuntimeError(
                "no history to save: compile/run with record_history=True"
            )
        target = path if path is not None else self.history_path
        if target is None:
            raise RuntimeError("no path given and Simulation.history_path is not set")
        return self.history.save(target)

    def write_outputs(self) -> None:
        """Write per-link and per-trip CSV outputs (and the history if enabled)."""
        if self.history is not None and self.history_path:
            self.history.save(self.history_path)

        if self.output_link_file:
            all_records: list[dict] = []
            if self.link_output_sample_time is None:
                self.link_output_sample_time = min(self.total_time, 60)
            for link in self.links:
                all_records.extend(
                    link.get_output_records(
                        self.link_output_sample_time,
                        self.time_step,
                        self.total_time,
                    )
                )

            with open(self.output_link_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=all_records[0].keys())
                writer.writeheader()
                writer.writerows(all_records)

        if self.trip_output_file:
            trip_records: list[dict] = []
            for node in self.nodes:
                trip_records.extend(node.get_arrived_trips())

            with open(self.trip_output_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=trip_records[0].keys())
                writer.writeheader()
                writer.writerows(trip_records)
