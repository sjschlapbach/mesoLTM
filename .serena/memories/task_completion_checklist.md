# Task Completion Checklist

When finishing a coding task:

1. **Tests:** `pytest` (add/adjust tests for new behaviour).
2. **Lint + format:** `pylint src/mesoltm examples` and `black --check src examples`.
3. **Types:** `mypy src`.
4. **Docs — keep BOTH doc sets in sync:** if the change touches the public API,
   model/behaviour, interfaces, CLI, or scenario schema, update **both** the user
   docs (`docs/`, the MkDocs Material site) **and** the AI-agent docs (`ai-docs/`,
   indexed by `context7.json`, incl. `ai-docs/api-reference.md`). The
   docstring-driven API-reference pages regenerate themselves; the narrative pages
   and the `ai-docs/` files do **not** — edit them by hand. Then verify with
   `mkdocs build --strict` (see `mem:suggested_commands`).
5. **Update tracking:**
   - Update the relevant **serena memory** if reference facts changed: `mem:codebase_structure` (structure), `mem:code_style_and_conventions` (style/tooling), `mem:suggested_commands` (commands).
   - Append a dated entry to `.ai/PROGRESS.md` — **always**.
   - Add to `.ai/DECISIONS.md` if you made a systematic/non-obvious choice.

Outstanding project follow-ups (e.g. registering the Zenodo DOI) are tracked in
dedicated memories such as `mem:pending_zenodo_doi` — check them when relevant.

See `mem:ai_tracking_system` for how knowledge is split. A `Stop` hook reminds you if work changed but tracking (`.ai/` or `.serena/memories/`) wasn't updated.
