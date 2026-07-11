# Links & the fundamental diagram

A [`Link`](../reference/core.md#links) is a directed road segment governed by a
**triangular fundamental diagram (FD)**. This page covers its parameters, the
sending/receiving flows, and the integer discretisation that makes the model
track whole vehicles.

## Parameters

`mesoltm` uses standard traffic-engineering notation for the FD (the values are
identical to the paper; only the symbol spellings differ — see
[Deviations §A5](deviations-from-the-paper.md)):

| Parameter | Symbol | Meaning | Units |
|-----------|--------|---------|-------|
| `v_f` | $v_f$ | Free-flow speed | m/s |
| `w` | $w$ | Backward shock-wave speed | m/s |
| `rho_jam` | $\rho_{\text{jam}}$ | Jam density | veh/m |
| `length` | $L$ | Link length | m |

Capacity (maximum flow) is **derived**, not set:

$$ \text{capacity} = \frac{\rho_{\text{jam}}\, v_f\, w}{v_f + w} \quad [\text{veh/s}] $$

```python
from mesoltm import Link

link = Link(link_id=1, length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)
# after the simulation starts the link, link.capacity == 1.0 veh/s
```

!!! warning "FD parameters live on the link, not the vehicle"
    `v_f`, `w`, and `rho_jam` are **link** properties. A `Vehicle` never carries
    them — see [Vehicles & routing](vehicles-and-routing.md).

## Occupancy thresholds

*Occupancy* is the number of vehicles on a link. `start()` also derives two
whole-vehicle thresholds from the FD, stored on the link for auxiliary
computations:

$$ \texttt{critical\_occupancy} = \big\lfloor \rho_{\text{crit}}\, L \big\rfloor
   \quad\text{with}\quad
   \rho_{\text{crit}} = \frac{\rho_{\text{jam}}\, w}{v_f + w} $$

$$ \texttt{jam\_occupancy} = \big\lfloor \rho_{\text{jam}}\, L \big\rfloor $$

$\rho_{\text{crit}}$ is the **critical density**, where the free-flow and congested
branches of the triangular FD meet ($\rho_{\text{crit}}\, v_f = \text{capacity}$).
Both thresholds are **floored downward** so the integer count is conservative: a
link holding at most `critical_occupancy` vehicles has density $\le
\rho_{\text{crit}}$ and is therefore still free-flowing, and `jam_occupancy` is the
most vehicles that physically fit (the same `rho_jam · length` storage that bounds
the receiving flow).

```python
link = Link(link_id=1, length=300.0, v_f=30.0, w=6.0, rho_jam=0.2)
# after start(): link.critical_occupancy == 10, link.jam_occupancy == 60
```

## Wave travel times

The FD's two wave speeds give two integer lags, in whole steps, that a link uses
to look back along its cumulative curves:

$$ T_1 = \left\lfloor \frac{L}{v_f\,\Delta t} \right\rfloor \qquad
   T_2 = \left\lfloor \frac{L}{w\,\Delta t} \right\rfloor $$

$T_1$ is the free-flow (forward) travel time; $T_2$ is the backward shock-wave
travel time. A vehicle that entered $T_1$ steps ago has, at free flow, reached the
downstream end; space freed by a vehicle that left $T_2$ steps ago has, via the
backward wave, reached the upstream end.

## Sending and receiving flows

Each step, from the cumulative inflow $F$ and outflow $G$ curves, the link computes
an integer **demand** (sending flow, ready to leave downstream) and **supply**
(receiving flow, room to accept upstream):

$$ \hat{D}(t) = \min\!\Big( \big\lfloor F(t - T_1 + 1) - G(t) \big\rfloor,\;
   \lfloor \hat{q}^{\,d}(t) \rfloor \Big) $$

$$ \hat{S}(t) = \min\!\Big( \big\lfloor G(t - T_2 + 1) + \rho_{\text{jam}} L - F(t) \big\rfloor,\;
   \lfloor \hat{q}^{\,u}(t) \rfloor \Big) $$

The first term of each is the free-flow/queue-storage quantity; the second caps it
by an integer capacity token (below). `rho_jam · length` is the link's jam
**storage** — the most vehicles it can hold.

## Integer capacity tokens

To keep flows integer while honouring the average capacity, each link maintains
two token buckets — one for discharge ($\hat{q}^{\,d}$), one for entry
($\hat{q}^{\,u}$). Each step they replenish by `capacity · dt` and are debited by
the actual flow, capped so they cannot accumulate unboundedly:

$$ \hat{q}(t+1) = \min\!\big( \hat{q}(t) + \text{capacity}\cdot\Delta t - \text{flow}(t),\;
   \lceil \text{capacity}\cdot\Delta t \rceil + 1 \big) $$

This token recursion is the mechanism that lets the continuous LTM be advanced one
whole vehicle at a time.

## The CFL condition

The discretisation is only valid if the fastest wave cannot cross the whole link
in less than one step (the Courant–Friedrichs–Lewy condition):

$$ \max(v_f, w)\cdot \Delta t \le L $$

Unlike the reference code, `mesoltm` **enforces** this: a link that violates it
raises a `ValueError` at `start()` explaining exactly how to fix it (shorten `dt`
or lengthen the link) rather than silently collapsing the lags.

```python
# Too-short link for dt = 1 s and v_f = 30 m/s: 30 * 1 > 20  ->  ValueError
Link(link_id=9, length=20.0, v_f=30.0, w=6.0, rho_jam=0.2)  # ok to build
# ... but sim.run()/start() raises with a clear message.
```

See [Deviations §A7](deviations-from-the-paper.md) for why this is a safe,
behaviour-preserving change.
