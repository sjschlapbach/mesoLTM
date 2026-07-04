# Decision log

> Append-only record of systematic or non-obvious decisions. **Newest first.** Protocol: see `CLAUDE.md`.
> Format per entry: date — decision — rationale — implications.

## 2026-07-04 — Controllers do one thing (rewrite routes); add `ReroutingController`

- **Decision:** give controllers a single responsibility — **optionally rewriting vehicle routes** — and move engine bookkeeping out of them. Removed the internal `_StepTracker` "controller"; the simulation loop (`Simulation._run_step`) now keeps `state.step` current itself (set to `t` before the phases, `t+1` after committing). Added `ReroutingController`: a pre-configured `Controller` that hands the user every in-network vehicle's location + remaining real-link route (`NetworkState.vehicles_in_network` → `VehicleView`) plus the state, and expects back `{vehicle: new_real_route}` for only the vehicles to change; omitted vehicles are untouched. Updates apply via `NetworkState.set_route` (validates the new route starts at the vehicle's current link — else `ValueError`, no silent stranding — and re-attaches the destination connector). Added `ShortestPathPolicy.route(state, a, b)` as a reusable full-route planner.
- **Rationale:** user found the controller setup unintuitive (a step-tracker masquerading as a controller; only a low-level `fn(t, state)` interface). Single responsibility + a "return only the routes you want changed" interface is far easier to reason about and is the natural fit for the ride-hail example's custom routing.
- **Implications:** `run()`/stepping behaviour unchanged (42→46 tests still green incl. regression; `state.step` semantics identical — pre-step reads see `t`, between-step reads see the committed `t+1`). `ReroutingController` works with the default route-following policy (it rewrites `vehicle.route`); it is a no-op if a live `RoutingPolicy` is the node router (that ignores `vehicle.route`). `FunctionController(fn, state=None)` is unchanged. Exported `ReroutingController`. See `docs/MODEL_CHANGES.md` B3.

## 2026-07-04 — Step-driven execution + dynamic vehicle injection (ride-hail framework hooks)

- **Decision:** add a step-at-a-time API and mid-run injection so external code (e.g. a ride-hail dispatcher) can drive the loop and add vehicles at a node during the run. `Simulation` gains `start()` / `step()` / `current_step` / `total_steps` alongside `run()` (now `start()` + a `step()` loop + `write_outputs()`); `Simulation.inject(node_id, vehicle, at_time=None)` → `NetworkState.inject` → `OriginNode.add_trip` appends a vehicle (routed over **real** link ids) to an origin's demand, splicing on the O/D connectors and inserting in departure-time order via `bisect.insort`. `Network.compile` gains `injection_budget: int = 0` to size connectors for static demand **plus** expected injections.
- **Rationale:** user needs the package as a framework for ride-hail simulation — track idle drivers externally, assign trips with custom logic, re-inject drivers at their current node into the next step's demand. A node with little/no static demand would otherwise get a connector sized to pass only ~1 veh/step (`vehicle_budget→max(1,·)`), throttling injection; `injection_budget` fixes this and only makes connectors *more* transparent (never binding), so static runs are unaffected.
- **Implications:** `run()` stays byte-exact (regression + a stepping-vs-`run()` equality test lock this). Injection at a non-origin raises `ValueError`; `step()` before `start()` or past the horizon raises `RuntimeError`. `network_state.step` is advanced to `current_step+1` at each step's end so injections/accessors read correct cumulative indices between steps. See `docs/MODEL_CHANGES.md` B5.

## 2026-07-04 — Trip travel time is total (includes access); access time reported separately

- **Decision:** `metrics.trip_record` now reports `travel_time` = **total** time in system (`arrival − start`), which **includes** the initial origin-queue + origin-connector wait. That access wait is surfaced separately as `access_time` (`network_entry − start`) and the in-network portion as `network_time` (`arrival − network_entry`); a `route` field lists the real links actually driven. Renamed the previous `queue_delay`→`access_time` and `departure_time`→`network_entry_time`; `summarize_trips` reports `mean_access_time`; the CSV gains `route`/`access_time`/`network_time`.
- **Rationale:** user request — connector/origin-queue time must count in a vehicle's travel time and be indicated, and a per-trip record must store vehicle id, route driven, total travel time, per-link times, and the initial waiting time. This reverses an earlier choice that excluded connector time from `travel_time`.
- **Implications:** field renames are a breaking change to the metrics dict/CSV (example + tests updated). For direct-attach origins with immediate release (all prior tests) access is 0, so `travel_time` values are unchanged there; the regression test is unaffected (it does not use these metrics).

## 2026-07-04 — Unprioritised merge/general nodes default to capacity-proportional priorities

- **Decision:** when a merge or general node is created with **neither** a `priority_vector` **nor** `alpha`, it now defaults its merge priorities to be **proportional to the inbound links' capacities** (max flow `rho_jam·v_f·w/(v_f+w)`), computed in the node's `start()` from `link.get_capacity()`. Previously the fallback was **equal** priority. This makes the node-level default match what the `Network` builder already did via `_alpha_for`, so the behaviour is consistent regardless of how the node is constructed. Nodes store only `priority_vector` now (the redundant `.alpha` attribute and the `resolve_priorities`/`alpha_from_priority_vector` helpers were removed).
- **Rationale:** user request — equal priority is rarely the intended default; capacity (lane-count) proportional yielding is the physically sensible one and matches the paper's stated use of priority vectors. Resolving in `start()` (after links' `start()`) is when capacities are known.
- **Implications:** only **unprioritised** nodes change (yield capacity-proportional instead of equal); every explicit `priority_vector`/`alpha` path — including all paper examples and the regression — is byte-for-byte unchanged. An unprioritised node's `priority_vector` is empty until `start()` runs (always called by `Simulation`). See `docs/MODEL_CHANGES.md` B2.

## 2026-07-04 — Connectors are transparent, unbounded entry buffers (queue lives on the connector)

- **Decision:** an auto-inserted O/D `ConnectorLink` is sized so it is never the binding constraint: `length = 1`, `v_f = w = 1/dt` (`T1 == T2 == 1`), `rho_jam = 2·N` with `N` = the scenario's total vehicle count. Storage (`2·N`) exceeds any possible queue and the per-step capacity token (`N`) exceeds any per-step flow, so the origin can always offload every waiting vehicle onto its source connector and the connector's own discharge never caps flow — the downstream junction (supply + merge priority) governs, exactly like a 1-lane link. This supersedes the previous connector sizing (fixed ~4-vehicle buffer + `4×` reference capacity). Metrics count time on a leading connector as `queue_delay`, not in-network `travel_time`.
- **Rationale:** user asked for minimum model impact — avoid queueing at the origin *and* on the connector at once, and avoid delaying a queued vehicle by a separate origin→connector hop. Moving the entry queue onto the connector (which is already part of the junction's demand) achieves both. The `N`-based budget has no `dt` term, so it does not shrink for larger time steps — removing the old buffer's dt-dependent-delay foot-gun. Verified feasibility numerically (nothing binds across dt/N) and behaviourally (origin queue stays 0 while the connector holds the queue; all vehicles arrive) before finalising.
- **Implications:** `ConnectorLink(link_id, time_step, vehicle_budget)` (no more `reference_capacity`/`buffer_vehicles`). `_alpha_for` weights a connector like the strongest real approach, so the large capacity does not distort merge priorities; routing costs use free-flow time, not capacity, so routing is unaffected. Paper validation scenarios use direct attachment (no connectors) and stay bit-exact. See `docs/MODEL_CHANGES.md` B1.

## 2026-07-04 — Time lives only in the simulation loop; links are time-stateless

- **Decision:** the `Link` keeps **no** time attributes (`time_step`, `total_time`, `total_steps`, `_current_step` all removed). The `Simulation` loop is the single source of truth for the clock and threads it through arguments: `update_state_variables(t, time_step)`, `get_output_records(sample_time, sim_time_step, total_time)`, and `set_inflow/set_outflow(..., step)` (nodes forward their step index for trajectory timestamps). `start(time_step, total_time)` consumes the values locally without storing them. This deviates from abmmeso (which stores time on the link) but is behaviour-preserving; see `docs/MODEL_CHANGES.md` A8.
- **Rationale:** user request — a link holding its own copy of the current step / step size risks going stale ("forgetting to update"); centralising time removes that failure mode. Verified up front that every consumer of the previously link-stored time could instead receive it as an argument, so the change was possible.
- **Implications:** `BaseLink`/`Link`/`ConnectorLink` and all node call sites use the new signatures; any future link subtype must accept time via these arguments rather than reading it off the instance. Node classes still carry set-once time config (out of scope; `OriginNode` needs `time_step` at step time). The exact regression test still passes.

## 2026-07-04 — Removed the continuous-time LTM; cite the repository first

- **Decision:** `mesoltm` now offers **only** the discrete/mesoscopic (individual-vehicle) LTM. Deleted the continuous single-commodity model (`core/continuous_link.py`, `core/continuous_nodes.py`) and the three discrete-vs-continuous comparison examples (`examples/paper_lane_drop.py`, `paper_diverge.py`, `paper_merge.py`), and dropped the six `Continuous*` symbols from the public API (`src/mesoltm/__init__.py`, `core/__init__.py`). This **supersedes** the 2026-07-03 "Include both models: discrete + continuous" decision. Separately, **citation guidance now names this repository as the primary reference**, with the paper as a secondary reference: reworked the README "Attribution and citation" section and the `NOTICE` cite line, and added a `CITATION.cff` (GitHub "Cite this repository").
- **Rationale:** user asked to focus the library solely on the discretized mesoscopic LTM (the abmmeso model) with easy-to-use interfaces, and to have people cite this repository first and the paper only secondarily.
- **Implications:** `paper_freeway.py` stays (discrete-only; its stray "discrete-vs-continuous" wording was cleaned). AGPL attribution to abmmeso/the paper is retained in per-file headers and `NOTICE` (license compliance is unchanged). `docs/MODEL_CHANGES.md` no longer lists a continuous model; B2 drops the continuous merge-node note. All gates stay green (pylint 10.00/10, black, mypy, 27 tests, examples, build). The append-only history above (which describes porting the continuous model) is left intact by design.

## 2026-07-04 — Lint with pylint (replaced ruff); split CI into per-gate workflows

- **Decision:** the linter is now **pylint** (ruff removed entirely, incl. its config and the `[dev]` entry). Config lives in `pyproject.toml` (`[tool.pylint.*]`): `good-names`/`good-names-rgxs` allow the short traffic-engineering identifiers (T1/T2/v_f/w/dt/g0…), `max-line-length = 88` mirrors black, and a documented `disable` list drops checks that fight the faithful port (long/branchy node loops, small classes, `no-else-*`, `unused-argument` for policy/controller callbacks, `use-dict-literal`, `wrong-import-position` for the examples' sys.path shim). CI is split into **separate workflows**: `lint.yml` (pylint), `format.yml` (black --check), `typecheck.yml` (mypy), `test.yml` (pytest 3.11/3.12), and a generic `release.yml` that builds on default-branch push with the PyPI publish step **commented out** for now.
- **Rationale:** user asked for pylint specifically and for separate, clearly-named CI actions plus a build/release action gated to main. Pylint's import-order/`wrong-import-order` covers basic import hygiene that ruff's isort previously enforced.
- **Implications:** import sorting is no longer auto-enforced (kept tidy manually + pylint's import-order checks). Lint CI installs `.[dev,plot]` so pylint resolves matplotlib. `black` still owns formatting. To publish, uncomment the release step (needs `PYPI_API_TOKEN` or a Trusted Publisher) — see B2 note in `release.yml`.

## 2026-07-03 — Merge priorities exposed as `alpha` shares, `priority_vector` kept internal

- **Decision:** Merge/general node priorities are the public interface as shares **`alpha_1, alpha_2, …`** (fractions of outbound supply per inbound link). The reference integer `priority_vector` remains the internal representation the ported node algorithm runs on; `core/priorities.py` interconverts. `Network` defaults `alpha` to capacity-proportional and exposes `set_merge_priorities(node_id, {link_id: share})` to override at node-definition time. The continuous merge node's `priorities` arg was renamed `alpha`.
- **Rationale:** `alpha` is the standard traffic-flow notation for merge priority shares and is what the user asked for; keeping the ported algorithm on its exact `priority_vector` preserves bit-exact fidelity (regression stays 0-diff).
- **Implications:** Nodes accept **either** `alpha=` or `priority_vector=` (equivalent) and expose both `.alpha` and `.priority_vector`. Prefer `alpha` in new code/examples. Capacity-proportional remains only a default, applied by the builder — explicit `priority_vector`s (paper examples) are untouched.

## 2026-07-03 — Relicensed to AGPL-3.0 (was MIT)

- **Decision:** `mesoltm` ships under **AGPL-3.0-or-later** (replaced the root MIT `LICENSE`; added `NOTICE` crediting de Souza et al. + DOI + upstream repo).
- **Rationale:** the package copies/adapts the core logic of `abmmeso` (AGPL-3.0), making it a derivative work; AGPL is copyleft and propagates.
- **Implications:** `pyproject.toml` declares `AGPL-3.0-or-later`; a permissive relicense would require the original author's permission or a clean-room rewrite.

## 2026-07-03 — Ported the discrete + continuous LTM verbatim; one intentional model seam

- **Decision:** ported the discrete (mesoscopic) and continuous single-commodity LTM from `abmmeso` with **identical arithmetic**. The **only** model change is that a branching node's next-link lookup is delegated to a pluggable `RoutingPolicy` (default reproduces the original). All other deviations are additive (auto O/D connector links, capacity-proportional default merge priorities, controller hook, shortest-path router) or behaviour-preserving (0-resets instead of None for typing; per-vehicle route `position`). Full list in `docs/MODEL_CHANGES.md`.
- **Rationale:** the brief mandates faithful dynamics ("change the model only where absolutely necessary") while enabling external routing/control on general graphs.
- **Implications:** a numeric regression test (`test_regression.py`) locks exact equality with `abmmeso` golden values; changing core arithmetic will break it.

## 2026-07-03 — Core LTM kept scalar (not vectorized); networkx added; black for formatting

- **Decision:** the ported LTM core stays scalar/integer Python (not vectorized NumPy) to guarantee bit-identical results; NumPy is used only for analysis/output. Added **networkx** as a core runtime dependency (graphs, grids, shortest-path routing). Switched the formatter from ruff-format to **black** (ruff kept for linting).
- **Rationale:** faithfulness overrides the "prefer vectorized NumPy on hot paths" convention for the core; networkx is standard for graph work; user requested black.
- **Implications:** `code_style_and_conventions` memory updated; CI runs `ruff check`, `black --check`, `mypy`, `pytest`, `python -m build`.

## 2026-07-03 — src layout with tests inside the package; examples outside; PyPI-ready

- **Decision:** package under `src/mesoltm/`; **tests live inside** the package (`src/mesoltm/tests/`, relative imports, shipped in the wheel); **examples live outside** `src/` and import the installed package. `pyproject.toml` carries full PyPI-ready metadata + `mesoltm` console entry point; publication prepared but not performed (local `pip install -e`).
- **Rationale:** explicit user instruction; keeps a clean, publishable layout.
- **Implications:** pytest `testpaths = ["src/mesoltm/tests"]`; connectors/O-D behaviour and routing are covered by tests alongside the regression.

## 2026-07-03 — Project scope: mesoscopic traffic flow model as a pip package

- **Decision:** Build a mesoscopic traffic flow model and distribute it as the pip package `mesoltm`.
- **Rationale:** Stated project goal.
- **Implications:** Library-first design (clean public API, packaging discipline), not an application/script.

## 2026-07-03 — Packaging & tooling defaults

- **Decision:** `src/` layout, hatchling build backend, PEP 621 `pyproject.toml`; **Python 3.11+**; core deps `numpy` + `scipy`; `matplotlib` as optional extra `[plot]`; `pytest` + `ruff` + `mypy` (dev extra). See the `code_style_and_conventions` serena memory.
- **Rationale:** Mainstream, low-friction scientific-Python packaging. 3.11+ and numpy+scipy chosen by the maintainer (dev happens in a 3.11 venv, so dev matches the floor).
- **Implications:** Scaffold accordingly on first code. Reversible, but changing the Python floor or build backend later is disruptive.

## 2026-07-03 — Serena is the primary reference store; `.ai/` keeps only logs

- **Decision:** Activated serena for the project (`.serena/project.yml`, `languages: [python, bash]`) and stored reference knowledge as committed serena memories: `project_overview`, `codebase_structure`, `code_style_and_conventions`, `suggested_commands`, `tools_and_skills`, `task_completion_checklist`, `ai_tracking_system`. Removed the now-duplicated `.ai/ARCHITECTURE.md` and `.ai/CONVENTIONS.md`; `.ai/` now holds only `DECISIONS.md` + `PROGRESS.md`. Trimmed `CLAUDE.md` to protocol + pointers.
- **Rationale:** Per user instruction — keep reference facts in serena memory (queryable, single source of truth) and only maintain separately what serena memory doesn't hold well (the append-only logs). Avoids duplicating the same facts in two places.
- **Implications:** Update memories via serena's `write_memory` when structure/conventions/commands change; append the `.ai/` logs for decisions/progress. The Stop hook now treats `.ai/` **or** `.serena/memories/` as a valid tracking update and uses `git status --untracked-files=all` so nested memory paths are detected. `.serena/project.yml` + memories are committed; `.serena/cache` and `project.local.yml` are git-ignored by serena's own `.gitignore`.

## 2026-07-03 — Expand the agent skill set for package development

- **Decision:** Beyond context7/serena/dataviz/verify/code-review/simplify, also use **run** (drive example scripts/CLI), **security-review** (before publishing to PyPI), and **review** (GitHub PRs). `fewer-permission-prompts`, `update-config`, `session-report` are occasional maintenance helpers. All ship with Claude Code and are on by default — no install step; documented in `CLAUDE.md`.
- **Rationale:** Cover the full library lifecycle (navigate → verify → review → security-review → release), which a publicly pip-installable package warrants.
- **Implications:** No config change needed to enable them; they're referenced in `CLAUDE.md` so agents reach for them at the right stage.

## 2026-07-03 — Use context7 + serena MCPs; pre-approve their read-only tools

- **Decision:** Standardize on the **context7 MCP** for library-doc lookup and the **serena MCP** (LSP-backed) for semantic code navigation/editing. Read-only tools of both, plus common Python dev commands, are allow-listed in `.claude/settings.json`. `dataviz`/`verify`/`code-review`/`simplify` skills are the go-to for viz/verification/review.
- **Rationale:** Optimize the repo for agent development — fewer permission prompts, current library docs instead of memory, symbol-level code intelligence.
- **Implications:** Prefer these over ad-hoc web search / text grep. Editing serena tools are intentionally left to prompt. Plugins are assumed enabled at the user level; pin them in `enabledPlugins` if teammates need them guaranteed.

## 2026-07-03 — Enforce tracking updates with a `Stop` hook

- **Decision:** A `Stop` hook (`.claude/hooks/ai-tracking-reminder.sh`) blocks Claude from finishing when the working tree has changes outside `.ai/` and `.ai/` was not updated, asking it to update the tracking docs (or commit) first.
- **Rationale:** Make "keep `.ai/` current" enforced, not just documented. The check is self-terminating (updating `.ai/` or committing clears it) so it cannot loop.
- **Implications:** Disable/edit via `/hooks` or by removing the `hooks.Stop` entry in `.claude/settings.json`. `.DS_Store` changes are ignored so they don't trigger it.

## 2026-07-03 — Keep agent tracking in `.ai/`, reserve `docs/` for users

- **Decision:** Store the AI tracking system in `.ai/`. `docs/` is reserved for user-facing documentation to be added later.
- **Rationale:** Separate agent context from human documentation so neither clutters the other.
- **Implications:** Do not put agent tracking under `docs/`. `CLAUDE.md` points at `.ai/`.

## 2026-07-03 — Adopt an AI tracking system

- **Decision:** Maintain agent-facing tracking docs (architecture, conventions, decisions, progress) in a dedicated directory, governed by a working protocol in `CLAUDE.md`.
- **Rationale:** Give coding agents persistent, quick-lookup context and enforce keeping it current, avoiding repeated full-repo re-reading and lost decisions.
- **Implications:** Every task must read the relevant files before starting and update them before finishing (see `CLAUDE.md`).

## 2026-07-03 — Local dev on Python 3.11 (stdlib `venv`)

- **Decision:** Use a local `venv/` on **Python 3.11** for development (currently 3.11.15 via Homebrew). Initially the venv was 3.13.9; switched to 3.11 so local dev matches the package floor (`requires-python >= 3.11`).
- **Rationale:** Developing on the minimum supported version catches 3.11-incompatible usage early.
- **Implications:** Recreate the venv with `python3.11 -m venv venv`. Keep package `requires-python` at `>=3.11`.
