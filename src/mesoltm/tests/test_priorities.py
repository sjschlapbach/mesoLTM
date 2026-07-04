# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Unit tests for the ``alpha`` -> ``priority_vector`` conversion helper.

``priority_vector_from_alpha`` is a mesoltm convenience: it turns priority
**shares** into the integer ``priority_vector`` that the (verbatim ``abmmeso``)
merge/general node algorithm consumes. abmmeso itself only accepts an explicit
``priority_vector``; the faithful paper reproductions pass such vectors directly,
so this helper only affects user-supplied ``alpha`` and the capacity-proportional
default. These tests pin its behaviour for both integer and fractional inputs.
"""

from __future__ import annotations

from ..core.priorities import priority_vector_from_alpha


def _counts(alpha: list[float]) -> list[int]:
    """Return how many slots each inbound index gets in the priority vector."""
    vec = priority_vector_from_alpha(alpha)
    return [vec.count(i) for i in range(len(alpha))]


def test_integer_alphas_give_proportional_counts():
    """Integer weights map to a vector whose slot counts match the weights."""
    assert _counts([3, 1]) == [3, 1]
    assert _counts([1, 3]) == [1, 3]
    assert _counts([2, 1, 1]) == [2, 1, 1]
    assert _counts([3, 2, 1]) == [3, 2, 1]


def test_float_fractions_below_one_are_exact_for_twelfth_denominators():
    """Fractions (<1, summing to 1) with denominators dividing 12 convert exactly."""
    assert _counts([0.75, 0.25]) == [3, 1]
    assert _counts([0.5, 0.5]) == [1, 1]
    assert _counts([1 / 3, 2 / 3]) == [1, 2]
    assert _counts([0.25, 0.25, 0.5]) == [1, 1, 2]
    assert _counts([0.5, 1 / 3, 1 / 6]) == [3, 2, 1]


def test_integer_and_float_same_ratio_give_identical_vector():
    """[3, 1] and [0.75, 0.25] describe identical shares -> identical vector."""
    assert priority_vector_from_alpha([3, 1]) == priority_vector_from_alpha(
        [0.75, 0.25]
    )


def test_shares_are_normalised_internally():
    """Scaling the shares (e.g. not summing to 1) does not change the result."""
    assert priority_vector_from_alpha([0.3, 0.1]) == priority_vector_from_alpha([3, 1])
    assert priority_vector_from_alpha([6, 2, 2]) == priority_vector_from_alpha(
        [3, 1, 1]
    )


def test_equal_shares_serve_each_inbound_once():
    """Equal priority yields a simple round-robin over all inbound links."""
    assert priority_vector_from_alpha([1, 1]) == [0, 1]
    assert priority_vector_from_alpha([1, 1, 1]) == [0, 1, 2]


def test_zero_share_still_gets_a_slot():
    """A 0 share is never fully starved (avoids a deadlocked approach)."""
    vec = priority_vector_from_alpha([1, 0])
    assert set(vec) == {0, 1}
    assert vec.count(0) > vec.count(1)


def test_all_zero_shares_fall_back_to_equal():
    """Degenerate all-zero input falls back to one slot per inbound link."""
    assert priority_vector_from_alpha([0, 0]) == [0, 1]
    assert priority_vector_from_alpha([0.0, 0.0, 0.0]) == [0, 1, 2]


def test_single_inbound():
    """A single inbound link is always the one served."""
    assert priority_vector_from_alpha([1]) == [0]
    assert priority_vector_from_alpha([0.42]) == [0]


def test_vector_covers_all_links_with_valid_indices():
    """The vector references exactly the inbound indices, each at least once."""
    for alpha in ([3.0, 1.0], [0.6, 0.2, 0.2], [1.0, 1.0, 1.0, 1.0], [0.1, 0.9]):
        vec = priority_vector_from_alpha(alpha)
        assert set(vec) == set(range(len(alpha)))
        assert all(0 <= i < len(alpha) for i in vec)


def test_counts_are_monotonic_in_alpha_even_when_approximate():
    """For fractions not expressible at the resolution the split is approximate,
    but a larger share must never receive fewer slots than a smaller one."""
    for alpha in ([0.6, 0.2, 0.2], [0.4, 0.35, 0.25], [0.1, 0.9], [5.0, 3.0, 1.0]):
        counts = _counts(alpha)
        counts_by_ascending_alpha = [c for _, c in sorted(zip(alpha, counts))]
        assert counts_by_ascending_alpha == sorted(counts_by_ascending_alpha)
