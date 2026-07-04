# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Plugins: external logic hooked into the simulation loop, run first each step.

A plugin is the framework's general extension point. Each step, before the node
models resolve flows, every registered plugin's :meth:`Plugin.run_step` is called
with the live :class:`~mesoltm.network.state.NetworkState` on ``self.state``. From
there a plugin can read the full network state and change many aspects of the
simulation for the step that is about to run — anything reachable through the
state or the objects it exposes (e.g. gate/close links by inflating a routing
cost the router reads, drive an external dispatcher, apply dynamic access rules,
run a local agent auction).

**Affecting the routing of individual vehicles.** A very common use is rerouting,
and it works *because of where routes are stored*: every vehicle carries its own
``route`` (an ordered list of ``link_id`` values) on the
:class:`~mesoltm.core.vehicle.Vehicle` object; the network and its node models
only *propagate* each vehicle along whatever route it currently holds. So a plugin
reroutes a single vehicle simply by rewriting that vehicle's ``route`` — no
special routing hook is needed, and other vehicles are unaffected. Because plugins
run first in the step, any route change is seen by the very same step's flow
resolution. (:class:`ReroutingPlugin` wraps this in a safe, minimal interface;
:meth:`~mesoltm.network.state.NetworkState.set_route` performs the rewrite with
validation.)

Three levels of interface, simplest last:

* :class:`Plugin` — subclass and override :meth:`run_step` for full control.
* :class:`FunctionPlugin` — wrap a plain ``fn(t, state)`` function.
* :class:`ReroutingPlugin` — the simplest: you are handed every in-network
  vehicle's location and current route plus the network state, and you return only
  the routes you want changed; everything else is left untouched.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..core.vehicle import Vehicle
    from ..network.state import NetworkState, VehicleView


class Plugin:
    """Base class for per-step simulation plugins (the loop's extension point).

    Subclass and override :meth:`run_step` to inspect the live
    :class:`NetworkState` (``self.state``) and act on the simulation before the
    node models resolve flows for the same step. Actions take effect immediately;
    for example, mutating ``vehicle.route`` on any in-network vehicle reroutes it,
    because vehicles carry and follow their own route (see the module docstring).

    Attributes:
        state: The network state view, or ``None`` until ``Network.compile`` wires
            it in.
    """

    def __init__(self, state: NetworkState | None = None) -> None:
        """Create a plugin.

        Args:
            state: Optional network state to read during ``run_step``; normally
                left ``None`` and attached automatically by ``Network.compile``.
        """
        self.state = state
        self.time_step: float = 0.0
        self.total_time: float = 0.0

    def start(self, time_step: float, total_time: float) -> None:
        """Record timing parameters at the start of the simulation."""
        self.time_step = time_step
        self.total_time = total_time

    def run_step(self, t: int) -> None:
        """Run the plugin for step ``t`` (override in subclasses)."""


class FunctionPlugin(Plugin):
    """Adapter turning a plain function into a plugin.

    Args:
        fn: Callable invoked each step as ``fn(t, state)``; it may act on the
            simulation, e.g. mutate ``vehicle.route`` on any in-network vehicle to
            reroute it, or flip an external flag a routing cost reads.
        state: The network state passed to ``fn``. May be omitted (``None``);
            ``Network.compile`` wires in the compiled network's state.
    """

    def __init__(
        self,
        fn: Callable[[int, NetworkState], None],
        state: NetworkState | None = None,
    ) -> None:
        super().__init__(state)
        self._fn = fn

    def run_step(self, t: int) -> None:
        """Invoke the wrapped function as ``fn(t, state)``."""
        assert self.state is not None
        self._fn(t, self.state)


# Signature of the reroute callback: (step, state, vehicles) -> {vehicle: route}.
# ``vehicles`` are the in-network vehicles (see NetworkState.vehicles_in_network);
# the returned routes are ordered *real* link ids and only for vehicles to change.
RerouteFn = Callable[
    [int, "NetworkState", "list[VehicleView]"], "dict[Vehicle, list[int]]"
]


class ReroutingPlugin(Plugin):
    """The simplest routing plugin: return only the routes you want to change.

    Each step you are handed a snapshot of every vehicle currently travelling on a
    real link — its location (current link), its destination, and the remaining
    real-link route — together with the read-only network state. You return a
    mapping ``{vehicle: new_real_link_route}`` containing **only** the vehicles
    whose route should change; every vehicle you omit keeps its current route.

    Correctness of an update: the returned route is a list of *real* link ids that
    the vehicle should follow from its current link onward, starting with the link
    it is on now (that is exactly how :attr:`VehicleView.route` is presented, so
    "return the view's route with a different tail" is always valid). The plugin
    re-attaches the destination's access connector and resynchronises the vehicle's
    position pointer via :meth:`NetworkState.set_route`, so the vehicle continues
    seamlessly onto the new route at its next node. A route that does not start with
    the vehicle's current link is rejected (see ``set_route``), which prevents
    silently stranding a vehicle.

    Use it either by passing a ``reroute`` function or by subclassing and
    overriding :meth:`reroute`.
    """

    def __init__(
        self,
        reroute: RerouteFn | None = None,
        state: NetworkState | None = None,
    ) -> None:
        """Create a rerouting plugin.

        Args:
            reroute: Optional ``reroute(t, state, vehicles) -> {vehicle: route}``
                callback. If omitted, override :meth:`reroute` in a subclass.
            state: Network state; normally attached by ``Network.compile``.
        """
        super().__init__(state)
        self._reroute = reroute

    def reroute(
        self, t: int, state: NetworkState, vehicles: list[VehicleView]
    ) -> dict[Vehicle, list[int]]:
        """Return ``{vehicle: new_real_link_route}`` for the vehicles to change.

        Override in a subclass, or pass a ``reroute`` callable to the constructor.
        """
        if self._reroute is None:
            raise NotImplementedError(
                "ReroutingPlugin needs a reroute function or an overridden "
                "reroute() method"
            )

        return self._reroute(t, state, vehicles)

    def run_step(self, t: int) -> None:
        """Collect in-network vehicles, ask for route updates, and apply them."""
        assert self.state is not None
        # Snapshot every in-network vehicle (location + remaining real route), let
        # the user pick which to reroute, then apply just those — vehicles left out
        # of the returned map are untouched, so unrelated traffic is unaffected.
        vehicles = self.state.vehicles_in_network()
        for vehicle, real_route in self.reroute(t, self.state, vehicles).items():
            self.state.set_route(vehicle, real_route)
