# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for per-step history recording (matplotlib-free)."""

from __future__ import annotations

from ..core.vehicle import Vehicle
from ..network.builders import corridor_network, grid_network
from ..network.network import Network
from ..plugins.plugin import ReroutingPlugin
from ..recording import SimulationHistory, record_run
from ..routing.shortest_path import ShortestPathPolicy


def _corridor_with_vehicle():
    """Compile a 3-link corridor with one recorded vehicle departing at t=1."""
    net = corridor_network([200.0, 200.0, 200.0])
    net.set_origin(
        "n0",
        [
            Vehicle(
                vehicle_id=0,
                origin="n0",
                destination="n3",
                route=[1, 2, 3],
                scheduled_departure=1.0,
            )
        ],
    )
    return net.compile(time_step=1.0, total_time=60.0, record_history=True)


def test_records_one_frame_per_step_plus_initial():
    """A recorded run captures the initial state plus one frame per step."""
    sim = _corridor_with_vehicle()
    sim.run()
    assert sim.history is not None
    assert len(sim.history.frames) == sim.total_steps + 1


def test_history_off_by_default():
    """Without record_history the run captures nothing."""
    net = corridor_network([200.0])
    net.set_origin("n0", [Vehicle(vehicle_id=0, route=[1], scheduled_departure=0.0)])
    sim = net.compile(time_step=1.0, total_time=20.0)
    sim.run()
    assert sim.history is None


def test_agent_visits_links_in_route_order_with_logged_remaining_route():
    """The agent moves 1->2->3; the logged remaining route shrinks accordingly."""
    sim = _corridor_with_vehicle()
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile
    visited: list = []
    for frame in sim.history.frames:
        for agent in frame.agents:
            if not visited or visited[-1] != agent.link_id:
                visited.append(agent.link_id)
            # The remaining route is read straight off vehicle.route: it starts at
            # the current link and shrinks by one each hop.
            if agent.link_id == 1:
                assert agent.route == [1, 2, 3]
                assert agent.next_link_id == 2
            if agent.link_id == 2:
                assert agent.route == [2, 3]
                assert agent.next_link_id == 3
            # On the last real link only the current link remains -> no next hop.
            if agent.link_id == 3:
                assert agent.route == [3]
                assert agent.next_link_id is None
    assert visited == [1, 2, 3]


def test_classify_flows_into_category():
    """A classify callback sets each captured agent's colour category."""
    net = corridor_network([200.0, 200.0])
    net.set_origin(
        "n0",
        [
            Vehicle(
                vehicle_id=7, destination="n2", route=[1, 2], scheduled_departure=0.0
            )
        ],
    )
    sim = net.compile(time_step=1.0, total_time=40.0, record_history=True)

    sim.history_classify = lambda vehicle, state: f"veh{vehicle.vehicle_id}"
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile
    categories = {a.category for f in sim.history.frames for a in f.agents}
    assert categories == {"veh7"}


def test_origin_queue_is_captured_as_waiting():
    """When a tight link cannot admit every departure, the queue is captured."""
    # A low-capacity link cannot admit every simultaneous departure, so some
    # vehicles wait in the origin's vertical queue -> captured as "waiting".
    net = Network(default_fd={"v_f": 15.0, "w": 5.0, "rho_jam": 0.15})
    net.add_node("a", pos=(0.0, 0.0))
    net.add_node("b", pos=(1.0, 0.0))
    net.add_link("a", "b", length=200.0, rho_jam=0.02)  # low-capacity bottleneck
    vehicles = [
        Vehicle(
            vehicle_id=i,
            origin="a",
            destination="b",
            route=[1],
            scheduled_departure=0.0,
        )
        for i in range(8)
    ]
    net.set_origin("a", vehicles)
    net.set_destination("b")
    sim = net.compile(time_step=1.0, total_time=120.0, record_history=True)
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile

    waiting_frames = [f for f in sim.history.frames if f.waiting]
    assert waiting_frames, "expected an entry queue to form at the origin"
    sample = waiting_frames[0].waiting[0]
    assert sample.node_id == "a"
    assert sample.route == [1]
    assert sample.next_link_id == 1


def test_vehicle_props_are_captured_and_roundtrip(tmp_path):
    """A vehicle's props metadata is logged on its snapshots and survives JSON."""
    net = corridor_network([200.0, 200.0, 200.0])
    net.set_origin(
        "n0",
        [
            Vehicle(
                vehicle_id=0,
                origin="n0",
                destination="n3",
                route=[1, 2, 3],
                scheduled_departure=1.0,
                props={"cls": "truck", "vot": 9},
            )
        ],
    )
    sim = net.compile(time_step=1.0, total_time=60.0, record_history=True)
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile

    agents = [a for f in sim.history.frames for a in f.agents]
    assert agents and all(a.props == {"cls": "truck", "vot": 9} for a in agents)

    path = str(tmp_path / "hist.json")
    sim.history.save(path)
    loaded = SimulationHistory.load(path)
    reloaded = [a for f in loaded.frames for a in f.agents]
    assert reloaded and all(a.props == {"cls": "truck", "vot": 9} for a in reloaded)


def test_history_save_load_roundtrip(tmp_path):
    """A saved history reloads with the same frames, dt and node positions."""
    sim = _corridor_with_vehicle()
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile
    path = str(tmp_path / "hist.json")
    sim.history.save(path)
    loaded = SimulationHistory.load(path)
    assert len(loaded.frames) == len(sim.history.frames)
    assert loaded.time_step == sim.history.time_step
    # Node positions round-trip (ids become strings on load).
    assert loaded.node_positions["n0"] == (0.0, 0.0)


def test_record_run_convenience():
    """record_run enables logging, runs the sim and returns the history."""
    net = corridor_network([200.0, 200.0])
    net.set_origin("n0", [Vehicle(vehicle_id=0, route=[1, 2], scheduled_departure=0.0)])
    sim = net.compile(time_step=1.0, total_time=40.0)
    history = record_run(sim)
    assert isinstance(history, SimulationHistory)
    assert len(history.frames) == sim.total_steps + 1


def test_policy_routed_vehicle_logs_no_fabricated_plan():
    """Pure node-by-node routing stores no plan, so the recorder logs none.

    A :class:`ShortestPathPolicy` decides each vehicle's next link at every node
    and never writes a ``route`` back onto the vehicle. The recorder must not
    fabricate one (which would duplicate — and could diverge from — the routing
    logic): it logs ``vehicle.route`` verbatim, which is empty here.
    """
    net = grid_network(3, 3, link_length=100.0, all_nodes_od=True)
    net.set_origin(
        (0, 0),
        [
            Vehicle(
                vehicle_id=0, origin=(0, 0), destination=(2, 2), scheduled_departure=0.0
            )
        ],
    )
    sim = net.compile(
        time_step=1.0,
        total_time=120.0,
        routing_policy=ShortestPathPolicy(dynamic=True),
        record_history=True,
    )
    sim.run()
    assert sum(len(n.get_arrived_trips()) for n in sim.nodes) == 1
    assert sim.history is not None  # record_history=True was set at compile
    # No plan is stored on the vehicle -> the log carries no route / next link.
    agents = [a for f in sim.history.frames for a in f.agents]
    assert agents, "the vehicle should appear on real links"
    assert all(a.route == [] and a.next_link_id is None for a in agents)


def test_logged_route_matches_midrun_reroute():
    """The logged route is exactly what ran, even when rewritten mid-run.

    A vehicle planned via B is diverted onto the C path by a plugin. Because the
    recorder logs ``vehicle.route`` as-is (never recomputing), the driven path in
    the log is the rerouted one and the via-B links are never actually travelled —
    the log cannot drift from what the simulation did.
    """
    net = Network()
    a_m = net.add_link("A", "M", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    m_b = net.add_link("M", "B", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    b_d = net.add_link("B", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    m_c = net.add_link("M", "C", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    c_d = net.add_link("C", "D", length=300.0, v_f=15.0, w=5.0, rho_jam=0.15)
    net.set_destination("D")
    net.set_origin("A", vehicles=[Vehicle(vehicle_id=1, route=[a_m, m_b, b_d])])

    def reroute(_t, _state, vehicles):
        return {
            v.vehicle: [a_m, m_c, c_d]
            for v in vehicles
            if v.link_id == a_m and m_b in v.route
        }

    sim = net.compile(
        time_step=1.0,
        total_time=200.0,
        plugins=[ReroutingPlugin(reroute)],
        record_history=True,
    )
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile

    visited: list = []
    on_links: set = set()
    for frame in sim.history.frames:
        for agent in frame.agents:
            on_links.add(agent.link_id)
            if not visited or visited[-1] != agent.link_id:
                visited.append(agent.link_id)
            # Once diverted onto C, the log tracks the C tail (never the B path).
            if agent.link_id == m_c:
                assert agent.route == [m_c, c_d]
    assert visited == [a_m, m_c, c_d]  # the driven path is the rerouted one
    assert m_b not in on_links and b_d not in on_links  # B path never travelled
