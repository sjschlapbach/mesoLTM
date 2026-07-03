# Tools & Skills (Claude Code)

Prefer these over ad-hoc approaches:

- **context7 MCP** — up-to-date library docs. Call `resolve-library-id` then `query-docs`. Use before any unfamiliar or version-sensitive `numpy`/`scipy`/tooling API; do not code library calls from memory.
- **serena MCP** — semantic code intelligence (this server, LSP-backed for Python). Once code exists: `get_symbols_overview`, `find_symbol`, `find_referencing_symbols`, and symbol-level edits (`replace_symbol_body`, `rename_symbol`, `safe_delete_symbol`). Built-in `LSP` tool is an alternative for position-based queries.
- **dataviz skill** — before any fundamental diagram, space–time plot, or other visualization of model output.
- **verify skill** — exercise the affected flow end-to-end before committing nontrivial changes.
- **run skill** — drive example scripts / a CLI to confirm real behaviour, not just unit tests.
- **code-review / simplify skills** — on the working diff (correctness / cleanup).
- **security-review skill** — before tagging a release / publishing to PyPI.
- **review skill** — GitHub PR review (`/code-review` for the local working diff).

Maintenance helpers (occasional): **fewer-permission-prompts**, **update-config**, **session-report**.

All ship with Claude Code and are enabled by default — no install step. Read-only serena/context7 tools are pre-approved in `.claude/settings.json`.
