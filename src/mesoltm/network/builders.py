# mesoltm — mesoscopic Link Transmission Model
# Copyright (C) 2026 Julius Schlapbach
#
# This file is part of mesoltm and is licensed under the GNU Affero General
# Public License v3.0 or later; see the LICENSE and NOTICE files. mesoltm
# implements the model of de Souza et al., Simulation Modelling Practice and
# Theory 140 (2025) 103088 (https://doi.org/10.1016/j.simpat.2025.103088).

"""Convenience builders for common and custom network layouts."""

from __future__ import annotations

from collections.abc import Iterable

from .network import Network


def corridor_network(
    lengths: list[float],
    fd: dict | None = None,
    node_prefix: str = "n",
) -> Network:
    """Build a linear corridor of consecutive links with an origin and destination.

    Args:
        lengths: Length (m) of each link in order; ``len(lengths)`` links and
            ``len(lengths) + 1`` nodes are created.
        fd: Optional fundamental-diagram params applied to all links.
        node_prefix: Prefix for the generated node ids (``n0``, ``n1``, ...).

    Returns:
        A :class:`Network` with the first node set as origin and the last as
        destination (no demand attached yet — use ``set_origin`` to add vehicles).
    """
    net = Network(default_fd=fd)
    node_ids = [f"{node_prefix}{i}" for i in range(len(lengths) + 1)]
    for i, length in enumerate(lengths):
        net.add_node(node_ids[i], pos=(float(i), 0.0))
        net.add_node(node_ids[i + 1], pos=(float(i + 1), 0.0))
        net.add_link(node_ids[i], node_ids[i + 1], length=length)
    net.set_origin(node_ids[0])
    net.set_destination(node_ids[-1])
    return net


def grid_network(
    rows: int,
    cols: int,
    link_length: float = 200.0,
    spacing: float = 1.0,
    fd: dict | None = None,
    bidirectional: bool = True,
    skip_nodes: Iterable[tuple] | None = None,
    skip_edges: Iterable[tuple] | None = None,
    all_nodes_od: bool = False,
) -> Network:
    """Build a rectangular grid, optionally partial (missing nodes/edges).

    Nodes are ``(i, j)`` tuples for row ``i`` and column ``j``. Adjacent nodes are
    connected horizontally and vertically; with ``bidirectional`` a link is added
    in each direction. Custom / partially-connected layouts are supported by
    excluding nodes (``skip_nodes``) or individual directed edges (``skip_edges``).

    Args:
        rows: Number of grid rows.
        cols: Number of grid columns.
        link_length: Length (m) assigned to every grid link.
        spacing: Geometric spacing between nodes (for positions/plots).
        fd: Optional fundamental-diagram params for all links.
        bidirectional: If ``True`` add both directions of each edge.
        skip_nodes: Iterable of ``(i, j)`` nodes to omit entirely.
        skip_edges: Iterable of directed ``((i, j), (k, l))`` edges to omit.
        all_nodes_od: If ``True`` mark every present node as both origin and
            destination.

    Returns:
        A :class:`Network` describing the (possibly partial) grid.
    """
    net = Network(default_fd=fd)
    skip_nodes = set(skip_nodes or ())
    skip_edges = set(skip_edges or ())

    def present(node: tuple) -> bool:
        return 0 <= node[0] < rows and 0 <= node[1] < cols and node not in skip_nodes

    for i in range(rows):
        for j in range(cols):
            if (i, j) in skip_nodes:
                continue
            net.add_node((i, j), pos=(j * spacing, i * spacing))

    def maybe_link(a: tuple, b: tuple) -> None:
        if present(a) and present(b) and (a, b) not in skip_edges:
            net.add_link(a, b, length=link_length)

    for i in range(rows):
        for j in range(cols):
            if not present((i, j)):
                continue
            for nb in [(i, j + 1), (i + 1, j)]:
                if present(nb):
                    maybe_link((i, j), nb)
                    if bidirectional:
                        maybe_link(nb, (i, j))

    if all_nodes_od:
        for i in range(rows):
            for j in range(cols):
                if present((i, j)):
                    net.set_origin((i, j))
                    net.set_destination((i, j))
    return net


def network_to_dict(net: Network) -> dict:
    """Serialise a network's topology to a plain dict (JSON-friendly).

    Args:
        net: The network to serialise.

    Returns:
        A dict with ``nodes``, ``links``, ``origins`` and ``destinations``. Node
        ids are stringified so the result round-trips through JSON; demand
        vehicles are not included (attach them after loading).
    """
    # Same-package serialiser: reads the builder's internal topology directly.
    # pylint: disable=protected-access
    return {
        "nodes": [
            {"id": str(n), "pos": list(p) if p is not None else None}
            for n, p in net._positions.items()
        ],
        "links": [
            {
                "id": lid,
                "u": str(d["u"]),
                "v": str(d["v"]),
                "length": d["length"],
                "v_f": d["v_f"],
                "w": d["w"],
                "rho_jam": d["rho_jam"],
            }
            for lid, d in net._links.items()
        ],
        "origins": [str(n) for n in net._origins],
        "destinations": [str(n) for n in net._destinations],
    }


def network_from_dict(data: dict) -> Network:
    """Reconstruct a :class:`Network` from :func:`network_to_dict` output.

    Args:
        data: A dict with ``nodes``, ``links``, ``origins``, ``destinations``.

    Returns:
        The reconstructed network (without demand vehicles).
    """
    net = Network()
    for node in data.get("nodes", []):
        pos = tuple(node["pos"]) if node.get("pos") is not None else None
        net.add_node(node["id"], pos=pos)
    for link in data.get("links", []):
        net.add_link(
            link["u"],
            link["v"],
            length=link["length"],
            link_id=link.get("id"),
            v_f=link["v_f"],
            w=link["w"],
            rho_jam=link["rho_jam"],
        )
    for n in data.get("origins", []):
        net.set_origin(n)
    for n in data.get("destinations", []):
        net.set_destination(n)
    return net
