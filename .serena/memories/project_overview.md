# Project Overview

**mesoLTM** is a **mesoscopic (individual-vehicle) Link Transmission Model** for traffic flow, distributed as the pip package `mesoltm`. It is a faithful re-implementation of the discrete LTM of de Souza, Verbas, Auld & Tampère (SIMPAT 140 (2025) 103088; reference code `abmmeso`, AGPL-3.0), tracking every vehicle individually on general road networks, with pluggable per-vehicle routing, external simulation plugins (per-step loop hooks), parallel links/detours, and visualisations. Deviations from the paper are listed in `docs/MODEL_CHANGES.md`.

**Status:** v0.1 implemented and green (core ported with an exact numeric regression vs. `abmmeso`; network/routing/plugins/io/viz layers; examples; tests; CI). Installable locally (`pip install -e`); not yet published to PyPI.

**Runtime:** Python **3.11+** (dev in a 3.11.15 venv). Core deps `numpy`, `networkx`.

**License:** **AGPL-3.0-or-later** (adapts AGPL-3.0 source; see `LICENSE` + `NOTICE`).

See also: `mem:codebase_structure`, `mem:code_style_and_conventions`, `mem:suggested_commands`, `mem:tools_and_skills`, `mem:task_completion_checklist`, `mem:ai_tracking_system`.
