# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files.

"""Tests for the animation renderer (needs the optional [plot] extra)."""

from __future__ import annotations

import math

import pytest

matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

from ..core.vehicle import Vehicle  # noqa: E402
from ..network.builders import corridor_network  # noqa: E402
from ..visualizations import animation as anim  # noqa: E402


def _recorded_history() -> anim.SimulationHistory:
    """Record a short corridor run with four vehicles for rendering tests."""
    net = corridor_network([200.0, 200.0, 200.0])
    net.set_origin(
        "n0",
        [
            Vehicle(
                vehicle_id=i,
                destination="n3",
                route=[1, 2, 3],
                scheduled_departure=float(i),
            )
            for i in range(4)
        ],
    )
    sim = net.compile(time_step=1.0, total_time=80.0, record_history=True)
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile
    return sim.history


def test_expand_frame_indices_playback_speed():
    """subsample >1 repeats frames (slower), <1 drops them (faster), 1 is 1:1."""
    assert anim.expand_frame_indices(10, 2.0) == [
        i for i in range(10) for _ in range(2)
    ]
    assert anim.expand_frame_indices(10, 0.5) == [0, 2, 4, 6, 8]
    assert anim.expand_frame_indices(4, 1.0) == [0, 1, 2, 3]
    with pytest.raises(ValueError):
        anim.expand_frame_indices(4, 0.0)


def test_layout_and_render_frame():
    """A layout is built and a busy frame renders onto an axes."""
    history = _recorded_history()
    assert history is not None
    layout = anim.NetworkLayout.from_history(history)
    assert set(layout.positions) >= {"n0", "n1", "n2", "n3"}
    busiest = max(history.frames, key=lambda f: len(f.agents))
    ax = anim.render_frame(busiest, layout, highlight_links=[2])
    assert ax is not None
    matplotlib.pyplot.close(ax.figure)


def test_color_by_next_link_and_detail_levels():
    """Rendering supports next-link colouring and the detail presets/overrides."""
    history = _recorded_history()
    layout = anim.NetworkLayout.from_history(history)
    busy = max(history.frames, key=lambda f: len(f.agents))
    for ax in (
        anim.render_frame(busy, layout, color_by="next_link"),
        anim.render_frame(busy, layout, detail="minimal"),
        anim.render_frame(busy, layout, detail="full", show_node_labels=False),
    ):
        assert ax is not None
        matplotlib.pyplot.close(ax.figure)
    # next-link palette assigns a colour per distinct next link (stable over frames).
    assert anim.resolve_palette(history.frames, None, "next_link")


def test_color_by_none_is_uniform():
    """color_by=None collapses everything to the single default category."""
    history = _recorded_history()
    palette = anim.resolve_palette(history.frames, None, None)
    assert set(palette) == {anim.DEFAULT_CATEGORY}
    busy = max(history.frames, key=lambda f: len(f.agents))
    ax = anim.render_frame(
        busy, layout=anim.NetworkLayout.from_history(history), color_by=None
    )
    assert ax is not None
    matplotlib.pyplot.close(ax.figure)


def test_color_by_custom_callable_reads_props():
    """A callable color_by colours agents by arbitrary vehicle props metadata."""
    net = corridor_network([200.0, 200.0])
    net.set_origin(
        "n0",
        [
            Vehicle(
                vehicle_id=0,
                route=[1, 2],
                scheduled_departure=0.0,
                props={"cls": "van"},
            ),
            Vehicle(
                vehicle_id=1,
                route=[1, 2],
                scheduled_departure=0.0,
                props={"cls": "truck"},
            ),
        ],
    )
    sim = net.compile(time_step=1.0, total_time=60.0, record_history=True)
    sim.run()
    assert sim.history is not None  # record_history=True was set at compile

    def by_class(item):
        return item.props.get("cls", "car")

    palette = anim.resolve_palette(sim.history.frames, None, by_class)
    assert {"van", "truck"} <= set(palette)
    layout = anim.NetworkLayout.from_history(sim.history)
    busy = max(sim.history.frames, key=lambda f: len(f.agents))
    ax = anim.render_frame(busy, layout, color_by=by_class)
    assert ax is not None
    matplotlib.pyplot.close(ax.figure)


def test_opposing_links_are_fanned_onto_distinct_arcs():
    """Two links on the same edge get distinct arcs so their agents never coincide."""
    net = corridor_network([200.0, 200.0])
    rev = net.add_link("n1", "n0", length=200.0)  # reverse link on the n0<->n1 edge
    sim = net.compile(time_step=1.0, total_time=10.0)
    assert sim.network_state is not None  # attached by compile()
    layout = anim.NetworkLayout.from_state(sim.network_state)
    fwd = layout.links["1"]  # n0 -> n1
    rev_arc = layout.links[str(rev)]  # n1 -> n0, same physical edge
    chord = math.dist(fwd[0], fwd[1])
    # Both directions are drawn on the node centres, so their chords coincide...
    mid_fwd_edge = ((fwd[0][0] + fwd[1][0]) / 2, (fwd[0][1] + fwd[1][1]) / 2)
    mid_rev_edge = (
        (rev_arc[0][0] + rev_arc[1][0]) / 2,
        (rev_arc[0][1] + rev_arc[1][1]) / 2,
    )
    assert math.dist(mid_fwd_edge, mid_rev_edge) < 1e-9
    assert fwd[2] != 0.0 and rev_arc[2] != 0.0  # both curved (a lone link would be 0)
    # ... yet, drawn in opposite directions at equal curvature, they bow to opposite
    # sides, so their mid-points (where a lone agent sits) are clearly separated.
    bezier = anim._bezier_point  # pylint: disable=protected-access
    mid_fwd = bezier(fwd[0], fwd[1], fwd[2], 0.5)
    mid_rev = bezier(rev_arc[0], rev_arc[1], rev_arc[2], 0.5)
    assert math.dist(mid_fwd, mid_rev) > 0.1 * chord


def test_save_frames_writes_pngs(tmp_path):
    """save_frames writes one PNG per (strided) frame."""
    history = _recorded_history()
    assert history is not None
    layout = anim.NetworkLayout.from_history(history)
    paths = anim.save_frames(history.frames, layout, str(tmp_path / "f"), stride=10)
    assert paths
    assert all(p.endswith(".png") for p in paths)
    for p in paths:
        assert (tmp_path / "f" / p.rsplit("/", 1)[-1]).exists()


def test_save_animation_gif_and_frames_dir(tmp_path):
    """A GIF is written and, when frames_dir is given, the PNGs too."""
    history = _recorded_history()
    assert history is not None
    layout = anim.NetworkLayout.from_history(history)
    out = anim.save_animation(
        history.frames,
        layout,
        str(tmp_path / "clip.gif"),  # Pillow writer is always available
        fps=25,
        subsample=1.0,
        frames_dir=str(tmp_path / "pics"),
    )
    assert out.endswith(".gif")
    assert (tmp_path / "clip.gif").exists()
    # frames_dir requested -> the individual pictures are written too.
    assert list((tmp_path / "pics").glob("frame_*.png"))


def test_animate_from_missing_history_file_guides_user(tmp_path):
    """Rendering a missing history file explains how to enable logging."""
    missing = str(tmp_path / "nope.json")
    with pytest.raises(FileNotFoundError) as excinfo:
        anim.animate_from_history_file(missing, str(tmp_path / "out.mp4"))
    assert "record_history" in str(excinfo.value)


@pytest.mark.skipif(not anim.FFMpegWriter.isAvailable(), reason="ffmpeg not installed")
def test_save_animation_mp4(tmp_path):
    """With ffmpeg available, an MP4 is written."""
    history = _recorded_history()
    assert history is not None
    layout = anim.NetworkLayout.from_history(history)
    out = anim.save_animation(
        history.frames, layout, str(tmp_path / "clip.mp4"), fps=25
    )
    assert out.endswith(".mp4")
    assert (tmp_path / "clip.mp4").exists()
