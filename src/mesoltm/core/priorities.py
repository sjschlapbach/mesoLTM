# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Merge priority helper: turn ``alpha`` shares into an integer priority vector.

At a merge (or general) node the modeller thinks in terms of **priority shares**
``alpha_1, alpha_2, ...`` — the fraction of the downstream supply each inbound
link may claim. The reference discrete node algorithm (``abmmeso``) instead
consumes an integer ``priority_vector``: a circular list of inbound indices served
round-robin. :func:`priority_vector_from_alpha` translates shares into that vector,
so the public interface can be expressed as ``alpha`` (or, by default, as the
inbound links' capacities) while the ported node math keeps operating on the exact
``priority_vector`` it always did.
"""

from __future__ import annotations

import math


def priority_vector_from_alpha(alpha: list[float], resolution: int = 12) -> list[int]:
    """Build an integer, round-robin priority vector approximating ``alpha`` shares.

    Each inbound index ``i`` appears in the returned vector a number of times
    proportional to ``alpha_i``; iterating the vector round-robin therefore serves
    the inbound links in (approximately) their ``alpha`` proportions. The counts
    are reduced by their gcd to keep the vector short and interleaved so approaches
    are served in rotation rather than in blocks.

    Args:
        alpha: Non-negative priority shares, one per inbound link. They need not
            sum to exactly 1 (they are normalised internally); a share of 0 still
            receives a single slot so the approach is never fully starved.
        resolution: Granularity of the integer approximation (higher = finer).

    Returns:
        A circular ``priority_vector`` of inbound indices.
    """
    total = sum(alpha)
    if total <= 0:
        return list(range(len(alpha)))
    weights = [max(1, round(a / total * resolution)) for a in alpha]

    divisor = 0
    for w in weights:
        divisor = math.gcd(divisor, w)
    divisor = divisor or 1
    weights = [w // divisor for w in weights]

    vector: list[int] = []
    while any(weights):
        for idx, w in enumerate(weights):
            if w > 0:
                vector.append(idx)
                weights[idx] -= 1
    return vector
